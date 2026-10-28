import argparse,json,sys,zipfile,time
from pathlib import Path
import cv2,numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'SerialController/Commands/PythonCommands'))
from LocalFunction.LockOnDetection import SPECIES,detect_capture_name,detect_lockon
ASSETS=ROOT/'SerialController/Template/ZA_Story_PIC/LockOnNames'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--audit-zip',type=Path);args=parser.parse_args()
 rows=[]
 for expected,filename in [('mareep','mareep.png'),('scatterbug','scatterbug.png'),('pikachu','pikachu.jpg')]:
  image=cv2.imread(str(HERE/'evidence'/filename))
  for target in SPECIES:rows.append(dict(file=filename,actual=expected,**detect_capture_name(image,target,ASSETS)))
 curves=[]
 for mode,filename in [('mega','mega.jpg'),('normal','normal.jpg'),('mega','no_marker.jpg'),('mega','menu.jpg')]:curves.append(dict(file=filename,**detect_lockon(cv2.imread(str(HERE/'evidence'/filename)),mode)))
 (HERE/'results.json').write_text(json.dumps(dict(names=rows,contours=curves,opencv=cv2.__version__),ensure_ascii=False,indent=2),'utf8')
 print('Names',sum(r['matched'] for r in rows),'/',len(rows),'(3 expected positives); contours',[(r['file'],r['matched']) for r in curves],flush=True)
 if args.audit_zip:
  manifest=json.loads((ROOT/'reports/masked_template_20261026/audit_manifest.json').read_text('utf8'));rows=[];started=time.monotonic()
  with zipfile.ZipFile(args.audit_zip) as z:
   for i,item in enumerate(manifest):
    image=cv2.imdecode(np.frombuffer(z.read(item['member']),np.uint8),1)
    matches=[detect_capture_name(image,name,ASSETS) for name in SPECIES]
    rows.append(dict(source=item,results=matches))
    if i%100==0:print('audited',i,'/',len(manifest),flush=True)
  result=dict(frames=len(rows),hits=[r for r in rows if any(d['matched'] for d in r['results'])],rows=rows,seconds=time.monotonic()-started)
  (HERE/'archive_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8');print('Audit frames',len(rows),'hit frames',len(result['hits']),flush=True)
if __name__=='__main__':main()
