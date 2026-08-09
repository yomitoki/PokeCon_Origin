#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <d3d11.h>
#include <windows.graphics.capture.interop.h>
#include <windows.graphics.directx.direct3d11.interop.h>
#include <wrl/client.h>

#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Graphics.Capture.h>
#include <winrt/Windows.Graphics.DirectX.h>
#include <winrt/Windows.Graphics.DirectX.Direct3D11.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <string>

using Microsoft::WRL::ComPtr;
using namespace winrt;
using namespace winrt::Windows::Graphics::Capture;
using namespace winrt::Windows::Graphics::DirectX;
using namespace winrt::Windows::Graphics::DirectX::Direct3D11;

namespace {
constexpr wchar_t kMagic[] = L"PKWGC01";
constexpr size_t kHeaderSize = 512;
constexpr size_t kMappingSize = 64u * 1024u * 1024u;

#pragma pack(push, 1)
struct SharedHeader {
    wchar_t magic[8];
    volatile LONG sequence;
    volatile LONG status; // 0: starting, 1: frame ready, negative: error
    LONG width;
    LONG height;
    LONG stride;
    LONG frame_bytes;
    wchar_t error[232];
};
#pragma pack(pop)
static_assert(sizeof(SharedHeader) <= kHeaderSize, "shared header is too large");

void set_error(SharedHeader* header, LONG status, const std::wstring& message) {
    header->status = status;
    wcsncpy_s(header->error, message.c_str(), _TRUNCATE);
}

std::wstring hresult_message(HRESULT value) {
    wchar_t* buffer = nullptr;
    const DWORD flags = FORMAT_MESSAGE_ALLOCATE_BUFFER |
                        FORMAT_MESSAGE_FROM_SYSTEM |
                        FORMAT_MESSAGE_IGNORE_INSERTS;
    FormatMessageW(flags, nullptr, static_cast<DWORD>(value), 0,
                   reinterpret_cast<wchar_t*>(&buffer), 0, nullptr);
    std::wstring result = buffer ? buffer : L"Windows Graphics Capture error";
    if (buffer) LocalFree(buffer);
    return result;
}
} // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc = 0;
    auto argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv || argc < 4) return 2;

    const auto hwnd = reinterpret_cast<HWND>(_wcstoui64(argv[1], nullptr, 10));
    const std::wstring mapping_name = argv[2];
    const DWORD parent_pid = wcstoul(argv[3], nullptr, 10);
    LocalFree(argv);

    HANDLE mapping = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, mapping_name.c_str());
    if (!mapping) return 3;
    auto memory = static_cast<std::uint8_t*>(
        MapViewOfFile(mapping, FILE_MAP_ALL_ACCESS, 0, 0, kMappingSize));
    if (!memory) {
        CloseHandle(mapping);
        return 4;
    }
    auto header = reinterpret_cast<SharedHeader*>(memory);
    std::memset(memory, 0, kHeaderSize);
    std::memcpy(header->magic, kMagic, sizeof(kMagic));

    HANDLE parent = OpenProcess(SYNCHRONIZE, FALSE, parent_pid);
    try {
        if (!IsWindow(hwnd))
            throw hresult_error(E_INVALIDARG, L"選択したゲームウィンドウは終了しています。");
        init_apartment(apartment_type::multi_threaded);

        UINT flags = D3D11_CREATE_DEVICE_BGRA_SUPPORT;
#ifdef _DEBUG
        flags |= D3D11_CREATE_DEVICE_DEBUG;
#endif
        D3D_FEATURE_LEVEL levels[] = {
            D3D_FEATURE_LEVEL_11_1, D3D_FEATURE_LEVEL_11_0,
            D3D_FEATURE_LEVEL_10_1, D3D_FEATURE_LEVEL_10_0,
        };
        ComPtr<ID3D11Device> d3d_device;
        ComPtr<ID3D11DeviceContext> d3d_context;
        D3D_FEATURE_LEVEL selected_level{};
        check_hresult(D3D11CreateDevice(
            nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, flags,
            levels, ARRAYSIZE(levels), D3D11_SDK_VERSION,
            &d3d_device, &selected_level, &d3d_context));

        ComPtr<IDXGIDevice> dxgi_device;
        check_hresult(d3d_device.As(&dxgi_device));
        winrt::com_ptr<::IInspectable> inspectable;
        check_hresult(CreateDirect3D11DeviceFromDXGIDevice(
            dxgi_device.Get(), inspectable.put()));
        auto winrt_device = inspectable.as<IDirect3DDevice>();

        GraphicsCaptureItem item{nullptr};
        auto item_interop = get_activation_factory<
            GraphicsCaptureItem, IGraphicsCaptureItemInterop>();
        check_hresult(item_interop->CreateForWindow(
            hwnd, guid_of<GraphicsCaptureItem>(), put_abi(item)));

        auto size = item.Size();
        if (size.Width <= 0 || size.Height <= 0)
            throw hresult_error(E_FAIL, L"ゲームウィンドウの取得範囲がありません。");

        auto frame_pool = Direct3D11CaptureFramePool::CreateFreeThreaded(
            winrt_device, DirectXPixelFormat::B8G8R8A8UIntNormalized, 2, size);
        auto session = frame_pool.CreateCaptureSession(item);
        session.IsCursorCaptureEnabled(false);

        ComPtr<ID3D11Texture2D> staging;
        UINT staging_width = 0;
        UINT staging_height = 0;
        std::atomic<bool> closed{false};

        auto closed_token = item.Closed([&](auto&&, auto&&) {
            closed.store(true, std::memory_order_release);
        });
        auto frame_token = frame_pool.FrameArrived([&](auto const& sender, auto&&) {
            try {
                auto frame = sender.TryGetNextFrame();
                if (!frame) return;
                auto surface_access = frame.Surface().as<
                    ::Windows::Graphics::DirectX::Direct3D11::IDirect3DDxgiInterfaceAccess>();
                ComPtr<ID3D11Texture2D> texture;
                check_hresult(surface_access->GetInterface(
                    __uuidof(ID3D11Texture2D), reinterpret_cast<void**>(texture.GetAddressOf())));

                D3D11_TEXTURE2D_DESC desc{};
                texture->GetDesc(&desc);
                const size_t row_bytes = static_cast<size_t>(desc.Width) * 4u;
                const size_t frame_bytes = row_bytes * static_cast<size_t>(desc.Height);
                if (frame_bytes > kMappingSize - kHeaderSize) {
                    set_error(header, -4, L"ゲームウィンドウが映像バッファーの上限を超えています。");
                    return;
                }
                if (!staging || staging_width != desc.Width || staging_height != desc.Height) {
                    D3D11_TEXTURE2D_DESC staging_desc = desc;
                    staging_desc.BindFlags = 0;
                    staging_desc.MiscFlags = 0;
                    staging_desc.Usage = D3D11_USAGE_STAGING;
                    staging_desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
                    staging.Reset();
                    check_hresult(d3d_device->CreateTexture2D(&staging_desc, nullptr, &staging));
                    staging_width = desc.Width;
                    staging_height = desc.Height;
                }

                d3d_context->CopyResource(staging.Get(), texture.Get());
                D3D11_MAPPED_SUBRESOURCE mapped{};
                check_hresult(d3d_context->Map(
                    staging.Get(), 0, D3D11_MAP_READ, 0, &mapped));
                InterlockedIncrement(&header->sequence); // odd: writer owns buffer
                header->width = static_cast<LONG>(desc.Width);
                header->height = static_cast<LONG>(desc.Height);
                header->stride = static_cast<LONG>(row_bytes);
                header->frame_bytes = static_cast<LONG>(frame_bytes);
                auto output = memory + kHeaderSize;
                auto input = static_cast<const std::uint8_t*>(mapped.pData);
                for (UINT y = 0; y < desc.Height; ++y) {
                    std::memcpy(output + static_cast<size_t>(y) * row_bytes,
                                input + static_cast<size_t>(y) * mapped.RowPitch,
                                row_bytes);
                }
                d3d_context->Unmap(staging.Get(), 0);
                MemoryBarrier();
                header->status = 1;
                InterlockedIncrement(&header->sequence); // even: reader may copy
            } catch (const hresult_error& error) {
                set_error(header, -5, error.message().c_str());
            } catch (...) {
                set_error(header, -5, L"ゲーム映像を共有バッファーへ転送できませんでした。");
            }
        });

        session.StartCapture();
        while (!closed.load(std::memory_order_acquire) && IsWindow(hwnd)) {
            if (parent && WaitForSingleObject(parent, 0) != WAIT_TIMEOUT) break;
            Sleep(100);
        }
        frame_pool.FrameArrived(frame_token);
        item.Closed(closed_token);
        session.Close();
        frame_pool.Close();
        if (header->status >= 0) header->status = -2;
    } catch (const hresult_error& error) {
        set_error(header, -1, error.message().empty()
            ? hresult_message(error.code()) : std::wstring(error.message()));
    } catch (...) {
        set_error(header, -1, L"ゲーム専用キャプチャーを開始できませんでした。");
    }

    if (parent) CloseHandle(parent);
    UnmapViewOfFile(memory);
    CloseHandle(mapping);
    return 0;
}
