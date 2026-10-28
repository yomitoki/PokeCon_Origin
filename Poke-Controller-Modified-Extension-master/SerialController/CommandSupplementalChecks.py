"""Native, opt-in position checks. No Japanese glyphs authorize these actions."""
from pathlib import Path
import time

import cv2
import numpy as np


MENU_REFERENCES = {
    'POKEMON_ZA_POKEMON_MENU_X_MENU_W': 'pokemon_menu.png',
    'POKEMON_ZA_POKEMON_MENU_X_MENU_W_SELECT_SKILL': 'pokemon_menu_select_skill.png',
    'POKEMON_ZA_X_MENU_EVO_MENU': 'POKEMON_ZA_X_MENU_EVO_MENU.png',
    'POKEMON_ZA_SKILL_PAGE_WINDOW': 'skillpage.png',
}
BOSS_REFERENCES = {
    'POKEMON_ZA_MEGA_ABSOL_BATTLE_NAME': 'mega_absol_battle_name.png',
    'POKEMON_ZA_LAST_BATTLE_NAME': 'last_battle_name.png',
}
# This text target is used only by OUT_HOTEL_Z_45's approach correction.
# Keep the shared IN_ICON target's search area unchanged everywhere else.
HOTEL_REFERENCES = {
    'POKEMON_ZA_OUT_HOTEL_Z45_HOTEL_Z_TEXT': 'out_hotel_z45_hotel_z_text.png',
}
HOTEL_ICON_CROP = (300, 150, 900, 450)
HOTEL_ICON_THRESHOLD = .85
# Existing non-text registrations, evaluated on the very same input frame.
HUD_PATTERNS = {
    'field': [('field.png', (50,680,350,720), .80, False),
              ('field_back.png', (50,680,350,720), .85, False)],
    'battle': [('battle.png', (50,640,350,680), .75, True)],
    'escape': [('escape.png', (54,477,75,497), .85, True),
               ('escape_full_normal.png', (10,450,62,525), .85, True),
               ('escape_full_thin_red.png', (10,450,62,525), .85, True),
               ('escape_full_red.png', (10,450,62,525), .85, True)],
}
RETRY_TEXT_REFERENCES = {
    'farst_battle_retry_start.png',
    '2_select_tutorial.png', '3_select_tutorial.png', '3_select_select.png',
    'mega_retry_retry_question_prefix.png', 'mega_retry_hp_question_hp_prefix.png',
    'mega_retry_hp_question_choice_suffix.png',
    'mega_retry_hp_carryover_label_unselected.png',
    'mega_retry_hp_carryover_label_selected.png',
}
FIELD_PICTURES = (
    'POKEMON_ZA_FIELD_W', 'POKEMON_ZA_FIELD_BACK_W',
    'POKEMON_ZA_NO_BATTLE_FIELD_HARD_CHECK',
    'POKEMON_ZA_BATTLE_ACTIVE_LEVEL', 'POKEMON_ZA_ESCAPE',
)


def valid_frame(frame):
    return frame is not None and frame.shape == (720, 1280, 3)


def white_mask(frame, minimum=180, spread=40):
    """Neutral white in OpenCV, avoiding repeated Python-side channel scans."""
    b,g,r=cv2.split(frame)
    high=cv2.max(cv2.max(b,g),r)
    low=cv2.min(cv2.min(b,g),r)
    return cv2.bitwise_and(cv2.inRange(low,minimum,255),
                           cv2.inRange(cv2.subtract(high,low),0,spread))


def retry_panel(frame):
    """Return row count and selected row only, without reading any label."""
    if not valid_frame(frame):
        return None
    panel = frame[280:580, 900:1220]
    b, g, r = cv2.split(panel)
    white = white_mask(panel,160,45)!=0
    navy = ((b.astype(np.int16)-r >= 12) & (b >= 35) & (b <= 160) & (g < 135))
    mask = cv2.morphologyEx((white | navy).astype(np.uint8)*255,
                            cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    candidates = []
    for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]:
        x, y, w, h = cv2.boundingRect(contour)
        rows = round(h/52.0)
        if (140 <= w <= 310 and rows in (2, 3, 4) and abs(h-rows*52) <= 12
                and x > 0 and y > 0 and x+w < 320 and y+h < 300
                and cv2.contourArea(contour) >= w*h*.85):
            selected = [i for i in range(rows) if np.mean(
                white[y+int(i*h/rows)+7:y+int((i+1)*h/rows)-7, x+12:x+w-12]) >= .62]
            if len(selected) == 1:
                candidates.append(dict(rows=rows, selected=selected[0], bounds=(900+x, 280+y, w, h)))
    return candidates[0] if len(candidates) == 1 else None


class PositionChecks:
    def __init__(self, serial_root):
        self.root = Path(serial_root)
        self.images = {}

    def glyph(self, relative, frame, bounds, gray=True, exclusions=()):
        key=(relative,gray)
        if key not in self.images:
            raw = np.frombuffer((self.root/relative).read_bytes(), np.uint8)
            image = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('補足画像を読めません: '+relative)
            self.images[key] = image
        image = self.images[key]
        x1, y1, x2, y2 = bounds
        roi = frame[y1:y2, x1:x2]
        if gray:
            roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if roi.shape[0] < image.shape[0] or roi.shape[1] < image.shape[1]:
            return 0.0, (0, 0)
        scores = cv2.matchTemplate(roi, image, cv2.TM_CCOEFF_NORMED)
        height, width = image.shape[:2]
        for left, top, right, bottom in exclusions or ():
            left, top = max(0, left-x1-width+1), max(0, top-y1-height+1)
            right, bottom = min(scores.shape[1], right-x1), min(scores.shape[0], bottom-y1)
            if left < right and top < bottom:
                scores[top:bottom, left:right] = -2.0
        _, score, _, pos = cv2.minMaxLoc(scores)
        return float(score), (x1+pos[0], y1+pos[1])

    def hotel_icon(self, frame, exclusions=()):
        """Hotel-only lower extension; this icon does not prove entry success."""
        relative = 'Template/ZA_Story_PIC/Common/in_icon.png'
        result = dict(matched=False, score=0.0, threshold=HOTEL_ICON_THRESHOLD,
                      position=(0, 0), template_size=(30, 24),
                      search_crop=HOTEL_ICON_CROP, template_path=relative,
                      match_source='supplemental_hotel_icon')
        if not valid_frame(frame):
            return result
        score, position = self.glyph(relative, frame, HOTEL_ICON_CROP,
                                     exclusions=exclusions)
        height, width = self.images[(relative, True)].shape[:2]
        result.update(matched=score >= HOTEL_ICON_THRESHOLD, score=score,
                      position=position, template_size=(width, height))
        return result

    def hud_picture(self, kind, frame):
        observations=[]
        for filename,bounds,threshold,gray in HUD_PATTERNS[kind]:
            score,position=self.glyph('Template/ZA_Story_PIC/Common/'+filename,
                                      frame,bounds,gray=gray)
            observations.append(dict(reference=filename,score=score,
                                     threshold=threshold,position=position))
        return dict(matched=any(o['score']>=o['threshold'] for o in observations),
                    patterns=observations)

    def boss(self, name, frame, last_battle=False):
        result=dict(matched=False,score=0.0,threshold=1.0,position=(0,0),
                    template_size=(1,1),match_source='supplemental_battle_hud')
        if not valid_frame(frame) or name not in BOSS_REFERENCES:
            return result
        final=name=='POKEMON_ZA_LAST_BATTLE_NAME'
        if final and not last_battle:
            return result
        field=self.hud_picture('field',frame)
        observation=dict(field=field)
        if field['matched']:
            battle=self.hud_picture('battle',frame)
            escape=self.hud_picture('escape',frame) if not battle['matched'] else None
            hp=hp_fraction(frame)
            matched=bool(hp and (battle['matched'] or (escape and escape['matched'])))
            observation.update(battle=battle,escape=escape,hp=hp)
            # FIELD and BATTLE also match while walking with a Pokemon out.
            # The top boss bar prevents confirming that as the boss encounter.
            result.update(position=(10,450),template_size=(340,270))
        elif final:
            # Final event has no FIELD/Lv./escape HUD. Keep the existing
            # five-second gate and latch logic; replace only its name evidence.
            hp=hp_fraction(frame)
            observation['hp']=hp
            matched=hp is not None
            if hp:
                x,y,w,h=hp['bounds']
                result.update(position=(x,y),template_size=(w,h),
                              match_source='supplemental_boss_hp')
        else:
            matched=False
        result.update(matched=matched,score=1.0 if matched else 0.0,
                      observation=observation)
        return result

    @staticmethod
    def x_menu(frame):
        """Measure the six/seven-row popup and the highlighted row."""
        panel = frame[140:540, 550:1250]
        mask = cv2.morphologyEx(white_mask(panel), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        found = []
        for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]:
            x, y, w, h = cv2.boundingRect(c)
            if not (150 <= w <= 340 and 40 <= h <= 54):
                continue
            x, y = x+550, y+140
            selected = round(((y+h/2)-180)/52.0)
            if not 0 <= selected < 7 or abs(y+h/2-(180+52*selected)) > 6:
                continue
            # Find the lower edge from the popup's dominant dark fill, without
            # comparing any glyph shape. White profile/party panels fail it.
            row_counts = []
            for rows in (6, 7):
                bottom = 159+rows*52
                inside = frame[bottom-17:bottom-7, x+8:x+w-8].astype(np.int16)
                outside = frame[bottom+5:bottom+10, x+8:x+w-8].astype(np.int16)
                def blue(a):
                    return (a[:,:,0]-a[:,:,2] > 48) & (a[:,:,1]-a[:,:,2] > 8)
                if np.mean(blue(inside)) > .75 and np.mean(blue(outside)) < .45:
                    row_counts.append(rows)
            if len(row_counts) == 1 and selected < row_counts[0]:
                green = frame[max(0,y-6):y+h+6, max(0,x-20):x+22]
                hsv = cv2.cvtColor(green, cv2.COLOR_BGR2HSV)
                if np.count_nonzero(cv2.inRange(hsv,(30,100,130),(85,255,255))) >= 70:
                    found.append(dict(rows=row_counts[0], selected=selected, bounds=(x-6,150,w+12,row_counts[0]*52+9)))
        return found[0] if len(found) == 1 else None

    def skill_page(self, frame):
        # The white status header plus a cursor in a known move/list position
        # identifies the page. Move names (including Ice Beam) are not inferred.
        header = frame[65:155, 550:630]
        if np.mean(np.min(header,2) >= 175) < .85:
            return None
        regions = [
            ('list', (55,220,90,590)), ('X',(720,300,760,350)),
            ('Y',(560,360,600,400)), ('A',(880,360,930,400)),
            ('B',(720,410,760,460)),
        ]
        hits = []
        for slot, roi in regions:
            score, pos = self.glyph('Template/ZA_Story_PIC/Common/X_menu/side_select.png',frame,roi)
            if score >= .92:
                hits.append((slot, pos, score))
        if len(hits) != 1:
            return None
        slot, pos, score = hits[0]
        return dict(slot=slot, selected=(round((pos[1]-239)/52) if slot=='list' else slot),
                    bounds=(30,165,1220,500), score=score)

    def match(self, name, frame):
        result=dict(matched=False,score=0.0,threshold=1.0,position=(0,0),template_size=(1,1),match_source='supplemental_position')
        if not valid_frame(frame):
            return result
        if name == 'POKEMON_ZA_SKILL_PAGE_WINDOW':
            observation=self.skill_page(frame)
            matched=observation is not None
        else:
            observation=self.x_menu(frame)
            expected=(7,0) if name=='POKEMON_ZA_X_MENU_EVO_MENU' else (6,2) if name.endswith('SELECT_SKILL') else (6,0)
            matched=observation is not None and (observation['rows'],observation['selected'])==expected
        if observation:
            x,y,w,h=observation['bounds']
            result.update(position=(x,y),template_size=(w,h),observation=observation)
        result.update(matched=matched,score=1.0 if matched else 0.0)
        return result


def hp_fraction(frame):
    """Read the boss bar, not the player's numeric HP; unknown stays unknown."""
    if not valid_frame(frame):
        return None
    hsv=cv2.cvtColor(frame[80:113,416:867],cv2.COLOR_BGR2HSV)
    best=None
    for color,ranges in [
            ('GREEN',[((35,90,100),(100,255,255))]),
            ('YELLOW',[((18,100,140),(40,255,255))]),
            ('RED',[((0,100,100),(10,255,255)),((170,100,100),(179,255,255))])]:
        mask=np.zeros(hsv.shape[:2],np.uint8)
        for lower,upper in ranges:
            mask=cv2.bitwise_or(mask,cv2.inRange(hsv,lower,upper))
        columns=np.count_nonzero(mask[9:22],axis=0)>=11
        padded=np.pad(columns.astype(np.int8),(1,1))
        edges=np.flatnonzero(np.diff(padded))
        for start,end in zip(edges[::2],edges[1::2]):
            start,end=int(start),int(end)
            width=end-start
            if not (419<=416+start<=426 and 8<=width<=446):
                continue
            # A narrow, flat stripe at the fixed bar position. Broad red
            # dialogue backgrounds and bright effects are not HP evidence.
            if (np.mean(mask[1:6,start:end]>0)>.55
                    or np.mean(mask[27:32,start:end]>0)>.55):
                continue
            sample=frame[89:102,416+start:416+end].astype(np.int16)
            vertical=np.percentile(np.max(sample,axis=0)-np.min(sample,axis=0),90)
            if vertical>55:
                continue
            ratio=float(width)/(1280*.345)
            if best is None or ratio>best['ratio']:
                best=dict(ratio=ratio,color=color,bounds=(416+start,87,width,18))
    if best:
        # Check the empty part as well: an isolated colored window or sign
        # can resemble the fill, but does not form the full, flat HP stripe.
        track=frame[89:102,426:858].astype(np.int16)
        if np.percentile(np.max(track,axis=0)-np.min(track,axis=0),90)>55:
            return None
    return best


class RetryByPosition:
    """This command run's two sequences, learned only before attacking."""
    def __init__(self, checks):
        self.checks=checks
        self.reset()

    def reset(self, keep_strategy=False):
        learned=getattr(self,'learned',None) if keep_strategy else None
        next_strategy=getattr(self,'next_strategy','carry') if keep_strategy else 'carry'
        self.learned=learned
        self.next_strategy=next_strategy
        self.active=False
        self.black_since=None
        self.attempt=None
        self.hp_since=None
        self.hp_sample=None
        self.hp_started=None
        self.resume_wait_started=None

    @staticmethod
    def black(frame):
        return valid_frame(frame) and cv2.countNonZero(
            cv2.inRange(frame[:536,:912],(0,0,0),(24,24,24)))>=536*912*.985

    @staticmethod
    def question(frame):
        # Only a change detector, never a reference glyph or language classifier.
        gray=cv2.cvtColor(frame[570:625,340:760],cv2.COLOR_BGR2GRAY)
        return cv2.resize((gray>140).astype(np.uint8),(105,14),interpolation=cv2.INTER_AREA)

    def observe(self, frame):
        menu=retry_panel(frame)
        if menu is not None:
            return menu
        if not valid_frame(frame) or np.any(np.max(frame[280:550,900:1220],2)>24):
            return None
        score,_=self.checks.glyph('Template/ZA_Story_PIC/Common/arrow.png',frame,(900,620,990,680))
        if score>=.90:
            return dict(rows=0,selected=0,bounds=(900,280,320,270))
        return None

    def begin(self, last):
        strategy=self.learned or self.next_strategy
        if self.learned is None:
            self.next_strategy='full' if strategy=='carry' else 'carry'
        self.attempt=dict(strategy=strategy,last=last,stage=1,acked=False,gap=False,
                          question=None,ack=None,confirmed=0,dialogue_pages=0,
                          dialogue_question=None,dialogue_id=0)
        self.active=True
        self.hp_since=self.hp_started=self.hp_sample=None
        self.resume_wait_started=None
        print('[SUPPLEMENTAL_RETRY] begin strategy={} learned={}'.format(strategy,self.learned))

    def target(self, menu, stage):
        a=self.attempt
        if stage==2:
            return (0 if a['strategy']=='carry' else 1) if menu['rows']==3 else None
        # No-HP layouts: ordinary two rows / final battle three rows.
        if menu['rows']==(3 if a['last'] else 2):
            return 0
        if menu['rows']==(4 if a['last'] else 3):
            return 1 if a['strategy']=='carry' else 0
        return None

    def finish_hp(self, outcome):
        strategy=self.attempt['strategy']
        if outcome=='PARTIAL':
            self.learned=strategy
        elif outcome=='FULL':
            self.learned=None
            self.next_strategy='full' if strategy=='carry' else 'carry'
        print('[SUPPLEMENTAL_RETRY] resume={} strategy={} learned={} next={}'.format(outcome,strategy,self.learned,self.next_strategy))
        self.active=False
        self.black_since=None
        self.attempt=None
        self.hp_since=self.hp_started=self.hp_sample=None

    def resume(self, command, frame):
        now=time.monotonic()
        if self.hp_started is None:
            self.hp_started=now
        sample=hp_fraction(frame)
        outcome=('FULL' if sample and sample['ratio']>=.95 else 'PARTIAL' if sample and sample['ratio']<=.90 else 'UNKNOWN')
        if outcome!='UNKNOWN':
            old=self.hp_sample
            if old is None or old['outcome']!=outcome or abs(old['ratio']-sample['ratio'])>.025:
                self.hp_sample=dict(outcome=outcome,**sample)
                self.hp_since=now
            elif now-self.hp_since>=.5:
                self.finish_hp(outcome)
                return ''
        else:
            self.hp_sample=self.hp_since=None
        if now-self.hp_started>=2.0:
            # Never keep sampling after attacks have been allowed to resume.
            self.finish_hp('UNKNOWN')
            return ''
        command.wait(.1)
        return 'waiting'

    def step(self, command, reader, directions, button_a):
        command.checkIfAlive()
        try:
            frame=reader(command)
        except RuntimeError:
            frame=None
        if not valid_frame(frame):
            if self.active:
                command.wait(.1)
                return 'waiting'
            return ''
        black=self.black(frame)
        if not black:
            self.black_since=None
            if self.active and self.attempt and self.attempt['confirmed']:
                # Own the whole return-to-battle interval. Letting the caller
                # run while Lv. is temporarily missing could attack first and
                # then mistake the resulting damage for inherited HP.
                if command.image_check('POKEMON_ZA_HELP_MARKER'):
                    command.checkIfAlive()
                    command.pressRep(button_a,repeat=1,duration=.04,wait=0.0,interval=.1)
                    return 'waiting'
                if hp_fraction(frame) or any(command.image_check(p) for p in FIELD_PICTURES):
                    return self.resume(command,frame)
                if self.resume_wait_started is None:
                    self.resume_wait_started=time.monotonic()
                if time.monotonic()-self.resume_wait_started>=180:
                    self.finish_hp('UNKNOWN')
                    return ''
                command.wait(.1)
                return 'waiting'
            self.active=False
            self.attempt=None
            return ''
        self.active=True
        if any(command.image_check(p) for p in FIELD_PICTURES):
            self.black_since=None
            if self.attempt and self.attempt['confirmed']:
                return self.resume(command,frame)
            return ''
        now=time.monotonic()
        if self.black_since is None:
            self.black_since=now
        menu=self.observe(frame)
        if (self.attempt and self.attempt['acked'] and menu is None
                and cv2.countNonZero(cv2.inRange(frame[280:550,900:1220],
                                               (0,0,0),(24,24,24)))==270*320):
            # Count the next complete panel even if its question starts with
            # the same words in another language, or its arrow was not seen.
            self.attempt['gap']=True
        command.ZA_MOVE_LStick(*directions[:4],1,'END')
        command.ZA_MOVE_SEE(action='END',in_see_r=directions[4])
        command.ZA_ZL_ACTION('END')
        if now-self.black_since<5.0 or menu is None:
            command.wait(.1)
            return 'waiting'
        if self.attempt is None:
            self.begin(bool(getattr(command,'_za_mega_last_battle_mode',False)))
        a=self.attempt
        first_question=self.question(frame)
        command.wait(.08)
        command.checkIfAlive()
        try:
            fresh_frame=reader(command)
        except RuntimeError:
            fresh_frame=None
        fresh=self.observe(fresh_frame) if self.black(fresh_frame) else None
        if (not fresh or fresh['rows']!=menu['rows'] or fresh['selected']!=menu['selected']
                or any(abs(x-y)>3 for x,y in zip(fresh['bounds'],menu['bounds']))
                or any(command.image_check(p) for p in FIELD_PICTURES)):
            return 'waiting'
        question=self.question(fresh_frame)
        if float(np.mean(question!=first_question))>.025:
            return 'waiting'
        old=a['question']
        changed=old is not None and float(np.mean(question!=old))>.10
        if menu['rows'] and a['acked'] and (a['gap'] or changed):
            if a['stage']>=2:
                raise RuntimeError('補足再戦: 3つ目の選択画面を検出したため、位置を推測せず停止します。')
            a.update(stage=2,acked=False,gap=False,ack=None)
        if not menu['rows'] and a['acked']:
            a['gap']=True
        target=self.target(menu,a['stage']) if menu['rows'] else 0
        if target is None or (menu['rows'] and target>=menu['rows']):
            return 'waiting'
        if not menu['rows']:
            old_dialogue=a['dialogue_question']
            if old_dialogue is None or float(np.mean(question!=old_dialogue))>.10:
                a['dialogue_question']=question.copy()
                a['dialogue_id']+=1
        # Compression jitter must not clear A cooldown or the attempt limit.
        key=(a['stage'],menu['rows'],target,a['dialogue_id'] if not menu['rows'] else 0)
        ack=a['ack']
        if ack is None or ack['key']!=key:
            ack=dict(key=key,attempts=0,retry_at=0.0)
            a['ack']=ack
        now=time.monotonic()
        if now<ack['retry_at']:
            command.wait(.1)
            return 'waiting'
        if menu['selected']!=target:
            command.checkIfAlive()
            command.etc_sendCommand('Lbutton_up' if menu['selected']>target else 'Lbutton_down')
            command.wait(.2)
            print('[SUPPLEMENTAL_RETRY] stage={} rows={} selected={} -> row={}'.format(a['stage'],menu['rows'],menu['selected']+1,target+1))
            return 'moved'
        if ack['attempts']>=3:
            raise RuntimeError('補足再戦: 同じ画面でAを3回確認入力しても画面が進みません。')
        if not menu['rows'] and ack['attempts']==0:
            a['dialogue_pages']+=1
            if a['dialogue_pages']>10:
                raise RuntimeError('補足再戦: 黒コメントが10ページを超えたため停止します。')
        ack['attempts']+=1
        ack['retry_at']=now+.8
        if menu['rows']:
            a.update(acked=True,question=question.copy(),confirmed=max(a['confirmed'],a['stage']))
        command.checkIfAlive()
        command.pressRep(button_a,repeat=1,duration=.15,wait=.2,interval=.1)
        print('[SUPPLEMENTAL_RETRY] stage={} rows={} row={} strategy={} A={}/3'.format(a['stage'],menu['rows'],target+1,a['strategy'],ack['attempts']))
        return 'confirmed'
