"""Context-bound, non-language ZA scene checks for the opt-in native run."""
import time
import cv2
import numpy as np
try:
    from .CommandSupplementalChecks import hp_fraction
except ImportError:
    from CommandSupplementalChecks import hp_fraction

REFERENCES = {
    'POKEMON_ZA_FARST_BATTLE_RETRY_START': ('farst_battle_retry_start.png',),
    'POKEMON_ZA_TEXT_TRAIN_OUT_COMMENT': ('station_field.png',),
    'POKEMON_ZA_TEXT_STATION_LEAVE_COMMENT': ('station_leave_comment.png',),
    'POKEMON_ZA_OUT_HOTEL_Z23_FIELD_WHITE_COMMENT': ('out_hotel_z23_field_white_comment.png',),
    'POKEMON_ZA_LAST_BATTLE_CHARGE': ('last_battle_charge.png',),
    'POKEMON_ZA_LAST_BATTLE_STRONG_LIGHT': ('last_battle_strong_light.png',),
    'POKEMON_ZA_MORNING': ('morning.png',),
    'POKEMON_ZA_NIGHT': ('night.png',),
    'POKEMON_ZA_FURADARI_MAP': ('furadari_map.png',),
    'POKEMON_ZA_UG_SEWER_MAP': ('underground_sewer_map.png',),
    'POKEMON_ZA_MOVE_COMMENT_BATTLE': ('move_comment_battle.png',),
    'POKEMON_ZA_MOVE_COMMENT_BATTLE2': ('POKEMON_ZA_MOVE_COMMENT_BATTLE2.png',),
    'POKEMON_ZA_LOSE': ('lose.png', 'furadari_eyes_dark_comment.png'),
    'POKEMON_ZA_FURADARI_EYES_DARK_COMMENT': ('furadari_eyes_dark_comment.png',),
    'POKEMON_ZA_BOX_MENU': ('boxmenu.png',),
    'POKEMON_ZA_SELECT_ALL': ('select_all.png',),
    'POKEMON_ZA_LAST_BATTLE_MOVE_UI': ('last_battle_move_core_enforcer.png','last_battle_move_thousand_arrows.png','last_battle_move_thousand_waves.png','last_battle_move_lands_wrath.png'),
    'POKEMON_ZA_REWORD_END': ('reword_end.png',),
    'POKEMON_ZA_REWORD_LOSE': ('reword_lose.png',),
}


def white(a):
    return (np.min(a,2)>=180)&(np.max(a,2).astype(np.int16)-np.min(a,2)<=45)


def result(matched=False, **kw):
    d=dict(matched=bool(matched),score=float(bool(matched)),threshold=1.0,
           position=(0,0),template_size=(1,1),match_source='supplemental_scene')
    d.update(kw)
    return d


def clock_pentagon(frame, night=False):
    """Inspect only a coloured outline; the label inside is never sampled."""
    hsv=cv2.cvtColor(frame[:630,340:940],cv2.COLOR_BGR2HSV)
    lower,upper=((145,80,135),(175,255,255)) if night else ((80,55,150),(105,255,255))
    mask=cv2.inRange(hsv,lower,upper)
    # Fill glyph holes to locate the outer hull, then score just its rim.
    found=[]
    for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
        x,y,w,h=cv2.boundingRect(c)
        if not ((370<=w<=550 and 390<=h<=570) if night else (230<=w<=300 and 230<=h<=310)):continue
        if abs(x+w/2-300)>30 or not (65<=y<=155):continue
        hull=cv2.convexHull(c)
        poly=cv2.approxPolyDP(hull,.045*cv2.arcLength(hull,True),True)
        if len(poly)!=5:continue
        expected=np.array([[.5,0],[1,.38],[.81,1],[.19,1],[0,.38]])
        actual=(poly[:,0,:]-[x,y])/[w,h]
        corners=int(sum(np.min(np.linalg.norm(actual-p,axis=1))<=.11 for p in expected))
        outline=np.zeros_like(mask);cv2.drawContours(outline,[poly],-1,255,12)
        coverage=float(np.mean(mask[outline>0]>0))
        if corners>=4 and coverage>=.28:
            found.append(result(True,score=corners/5.,threshold=.8,position=(x+340,y),template_size=(w,h),observation={'corners':corners,'rim_color':coverage},match_source='supplemental_pentagon_4_of_5'))
    return found[0] if len(found)==1 else result()


class SceneChecks:
    def __init__(self, icons, choices):
        self.icons=icons
        self.choices=choices
        self.timers={}
        self.z23_bubble_templates = None
        self.reset_final_warning()

    def reset_final_warning(self):
        self.final_warning_key = None
        self.final_warning_deadline = 0.0

    def early_help(self, frame, threshold=.90):
        # Central lower cyan/green question mark only. The instructions below
        # it and the NPC/objective words elsewhere are deliberately excluded.
        return self.icons.simple(frame, 'early_help_question',
                                 (605, 545, 675, 630), threshold, False)

    def z23_obstacle_bubble(self, frame, command):
        """Match two non-text lower edges, only for Z_23's NPC avoidance.

        The caller already requires FIELD and EVENT search mode 2. The lower
        left corner and tail must belong to the same baseline; independent
        high scores elsewhere do not count. Width is allowed to vary with
        localization. No timer, dialogue classification or step success.
        """
        if getattr(command, '_1_story_current_state', '') != '1_STORY_OUT_HOTEL_Z_23':
            return result(match_source='supplemental_z23_bubble_context')
        bounds = (350, 100, 950, 350)  # Preserve the original search area.
        threshold = .90
        if self.z23_bubble_templates is None:
            loaded = []
            for asset in ('z23_bubble_lower_left', 'z23_bubble_tail'):
                path = self.icons.checks.root / ('Template/ZA_Story_PIC/Supplemental/' + asset + '.png')
                template = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
                if template is None:
                    raise ValueError('補足画像を読めません: ' + str(path))
                loaded.append(template)
            self.z23_bubble_templates = tuple(loaded)
        left, tail = self.z23_bubble_templates
        x0, y0, x1, y1 = bounds
        roi = frame[y0:y1, x0:x1]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        corners = cv2.matchTemplate(gray, left, cv2.TM_CCOEFF_NORMED)
        tails = cv2.matchTemplate(gray, tail, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where((corners >= threshold) &
                          (corners >= cv2.dilate(corners, np.ones((5, 5), np.uint8))))
        best = result(threshold=threshold, search_crop=bounds,
                      match_source='supplemental_z23_bubble_edges')
        # Bound the work even on a patterned or corrupt frame.
        candidates = sorted(zip(ys, xs), key=lambda p: float(corners[p]), reverse=True)[:32]
        for y, x in candidates:
            tx0, tx1 = x + 25, min(tails.shape[1], x + 400)
            ty0, ty1 = y + 6, min(tails.shape[0], y + 11)
            if tx0 >= tx1 or ty0 >= ty1:
                continue
            _, tail_score, _, pos = cv2.minMaxLoc(tails[ty0:ty1, tx0:tx1])
            tx, ty = tx0 + pos[0], ty0 + pos[1]
            score = min(float(corners[y, x]), tail_score)
            # Sample only blank interior adjacent to the two edges. Reject
            # yellow quest bubbles, which share the outline with white ones.
            patches = (roi[y:y+7, x+7:x+17], roi[ty:ty+3, tx+8:tx+24])
            neutral = all(float(np.mean(p.max(2).astype(np.int16) - p.min(2))) <= 45
                          for p in patches)
            if not neutral or score <= best['score']:
                continue
            best = result(score >= threshold, score=score, threshold=threshold,
                          position=(int(x+x0), int(y+y0)),
                          template_size=(int(tx+tail.shape[1]-x), int(ty+tail.shape[0]-y)),
                          search_crop=bounds,
                          observation=dict(corner_score=float(corners[y, x]), tail_score=tail_score,
                                           corner=(int(x+x0), int(y+y0)),
                                           tail=(int(tx+x0), int(ty+y0))),
                          match_source='supplemental_z23_bubble_edges')
        return best

    def first_battle_restart(self, frame, command):
        state = getattr(command, '_1_story_current_state', '')
        flow = getattr(command, '_za_story_battle_flows', {}).get(
            '1_STORY_FARST_BATTLE', {})
        # The portrait is also present in the initial battle and in the open
        # field. It can confirm a restart only inside an established defeat
        # recovery, or after battle -> result dialogue in this same battle.
        pending = (state == '1_STORY_FARST_BATTLE_LOSE'
                   or (state == '1_STORY_FARST_BATTLE'
                       and flow.get('active_seen')
                       and flow.get('result_comment_pending')))
        if not pending:
            return result(match_source='supplemental_first_restart_context')
        portrait = self.icons.simple(frame, 'first_battle_totodile',
                                     (45, 515, 150, 620), .85, False)
        help_icon = self.early_help(frame, .85)
        return result(portrait['matched'] and help_icon['matched'],
                      position=portrait['position'],
                      template_size=portrait['template_size'],
                      observation=dict(portrait=portrait, help=help_icon),
                      match_source='supplemental_first_restart_hud')

    def final_warning(self, frame, command):
        """One icon family, one extendable window; never classify the text.

        The two warnings overlap and the same enemy also announces the attack.
        Every fresh positive extends the window, including a stacked notice.
        A different silhouette on a red panel cannot extend it.
        """
        valid = frame is not None and frame.shape == (720, 1280, 3)
        eligible = (getattr(command, '_za_mega_last_battle_mode', False)
                    and getattr(command, '_za_mega_mode5_start_flag', 0) == 4)
        if not valid or not eligible:
            self.reset_final_warning()
            return result(valid=valid, active=False, visible=False, deadline=0.0)
        key = self.key(command)
        if key != self.final_warning_key:
            self.reset_final_warning()
            self.final_warning_key = key
        icon = self.icons.simple(frame, 'final_warning_enemy',
                                 (880, 175, 960, 355), .85, False)
        now = time.monotonic()
        if icon['matched']:
            # Observed first-to-second interval is about 4 s. Seven seconds
            # covers that gap plus margin; visibility refreshes the deadline.
            self.final_warning_deadline = now + 7.0
        active = now < self.final_warning_deadline
        return result(active, valid=True, active=active,
                      visible=bool(icon['matched']),
                      deadline=self.final_warning_deadline,
                      observation=icon,
                      match_source='supplemental_final_warning_window')



    @staticmethod
    def key(command):
        return tuple((k,str(v)) for k,v in sorted(vars(command).items())
                     if k.endswith('current_state'))

    def stable(self, label, matched, command, seconds):
        now=time.monotonic(); key=self.key(command); old=self.timers.get(label)
        if not matched:
            self.timers.pop(label,None);return False
        if old is None or old[0]!=key or now-old[2]>2.0:
            old=(key,now,now)
        self.timers[label]=(key,old[1],now)
        return now-old[1]>=seconds

    def other_map(self, frame):
        # Indoor-map icon + the B control + black map canvas. This identifies
        # OTHERMAP, not the Japanese name of a particular indoor location.
        icon=self.icons.simple(frame,'indoor_map',(25,5,100,65),.9)
        close=self.icons.simple(frame,'map_close_b',(1150,665,1230,720),.9)
        dark=float(np.mean(np.max(frame[100:500,150:1100],2)<40))
        return result(icon['matched'] and close['matched'] and dark>.30,
                      observation=dict(header=icon,close=close,dark=dark),
                      match_source='supplemental_other_map')

    def black_comment(self, frame, require_arrow=True):
        a=frame[560:670,310:980].astype(np.int16)
        navy=np.mean((a[:,:,0]-a[:,:,2]>15)&(a[:,:,0]>45)&(a[:,:,0]<175)&(a[:,:,1]<140))
        score,pos=self.icons.checks.glyph('Template/ZA_Story_PIC/Common/arrow.png',frame,(900,620,990,680))
        return navy>.65 and (not require_arrow or score>=.90)

    def map_warning(self, frame):
        map_visible=self.icons.simple(frame,'map_compass',(20,0,200,70))['matched'] or self.other_map(frame)['matched']
        if not map_visible or not self.black_comment(frame,require_arrow=False):return False
        if self.icons.map_menu(frame) is not None:return False
        # A dim/pulsing selection may fail the stricter actionable-row check.
        # Its possible presence is sufficient to defer a warning, never A.
        a=frame[400:550,920:1190].astype(np.int16)
        mask=(((a.min(2)>=110)&(a.max(2)-a.min(2)<=80))*255).astype(np.uint8)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
            _,_,w,h=cv2.boundingRect(c)
            if 140<=w<=260 and 35<=h<=55:return False
        # Dark areas of the ordinary night map can share the dialogue colour.
        # Require both non-text corners, with normal/indoor drawing variants.
        for variant in ('normal','indoor'):
            top=self.icons.simple(frame,'map_comment_'+variant+'_top',(961,552,999,594),.90,False)
            bottom=self.icons.simple(frame,'map_comment_'+variant+'_bottom',(961,656,999,695),.90,False)
            if top['matched'] and bottom['matched']:return True
        return False

    def menu(self, frame, kind):
        """Dedicated 6-row map filter or 7/8-row BOX menu; zero-based row."""
        is_map=kind=='filter'
        if is_map:
            if not (self.icons.simple(frame,'map_compass',(20,0,200,70))['matched'] or self.other_map(frame)['matched']):return None
            roi=(20,270,275,610); heights=(38,55);step=52;tops=(307,);counts=(6,)
        else:
            if not self.icons.simple(frame,'box_cube',(35,0,130,75))['matched']:return None
            roi=(20,60,560,680);heights=(29,42);step=36;tops=range(82,475);counts=(7,8)
        x0,y0,x1,y1=roi
        mask=(white(frame[y0:y1,x0:x1])*255).astype(np.uint8)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8));found=[]
        for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
            x,y,w,h=cv2.boundingRect(c);x+=x0;y+=y0
            if not (140<=w<=320 and heights[0]<=h<=heights[1]):continue
            cy=y+h/2
            hsv=cv2.cvtColor(frame[max(y-8,0):y+h+8,max(x-25,0):x+22],cv2.COLOR_BGR2HSV)
            if cv2.countNonZero(cv2.inRange(hsv,(30,100,130),(85,255,255)))<70:continue
            def navy(center):
                a=frame[int(center)-9:int(center)+9,x+8:x+w-8].astype(np.int16)
                return a.size>0 and np.mean((a[:,:,0]-a[:,:,2]>35)&(a[:,:,1]-a[:,:,2]>0)&(a[:,:,1]<(155 if is_map else 130)))>(.65 if is_map else .50)
            # BOX top is at a multiple of the row pitch relative to its highlight.
            candidates=tops if is_map else [cy-step*s for s in range(8)]
            for top in candidates:
                if top<80:continue
                selected=round((cy-top)/step)
                if abs(cy-(top+selected*step))>6:continue
                for rows in counts:
                    if not 0<=selected<rows or top+(rows-1)*step>650:continue
                    if not all(i==selected or navy(top+i*step) for i in range(rows)):continue
                    if navy(top-step) or navy(top+rows*step):continue
                    found.append(dict(rows=rows,selected=selected,bounds=(x-8,int(top-step/2-4),w+16,rows*step+8)))
        return found[0] if len(found)==1 else None

    def box_closed(self, frame):
        if not self.icons.simple(frame,'box_cube',(35,0,130,75))['matched']:return False
        highlights=(white(frame[80:680,20:550])*255).astype(np.uint8)
        highlights=cv2.morphologyEx(highlights,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        for c in cv2.findContours(highlights,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
            x,y,w,h=cv2.boundingRect(c)
            if 140<=w<=340 and 29<=h<=42:return False
        a=frame[70:680,20:550].astype(np.int16)
        mask=(((a[:,:,0]-a[:,:,2]>35)&(a[:,:,1]<130))*255).astype(np.uint8)
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
        # An unclassified popup must not fall through to a blind A.
        for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
            x,y,w,h=cv2.boundingRect(c)
            if 140<=w<=340 and 180<=h<=500 and cv2.contourArea(c)>w*h*.65:return False
        return True

    def match(self, name, frame, command):
        if name == 'POKEMON_ZA_OUT_HOTEL_Z23_FIELD_WHITE_COMMENT':
            return self.z23_obstacle_bubble(frame, command)
        if name == 'POKEMON_ZA_FARST_BATTLE_RETRY_START':
            return self.first_battle_restart(frame, command)
        early_states = {
            'POKEMON_ZA_TEXT_TRAIN_OUT_COMMENT': (
                '1_STORY_START_CHECK', '1_STORY_STATION_OUT'),
            'POKEMON_ZA_TEXT_STATION_LEAVE_COMMENT': (
                '1_STORY_STATION_FRONT', '1_STORY_STATION_LEAVE_MOVE',
                '1_STORY_BAG_CHASE_END'),
        }
        if name in early_states:
            if getattr(command, '_1_story_current_state', '') not in early_states[name]:
                return result(match_source='supplemental_early_help_context')
            return self.early_help(frame)
        if name in ('POKEMON_ZA_LAST_BATTLE_CHARGE',
                    'POKEMON_ZA_LAST_BATTLE_STRONG_LIGHT'):
            # Legacy consumers get the same window for either name. No
            # CHARGE -> STRONG_LIGHT text transition is required in this mode.
            return self.final_warning(frame, command)
        if name in ('POKEMON_ZA_REWORD_END','POKEMON_ZA_REWORD_LOSE'):
            # The caller handles white dialogue as an UNKNOWN result. Never
            # let a later Japanese-text branch classify it as a win or loss.
            return result(False,match_source='supplemental_result_unknown')
        if name=='POKEMON_ZA_LAST_BATTLE_MOVE_UI':
            if not getattr(command,'_za_mega_last_battle_mode',False) or hp_fraction(frame) is None:return result()
            if self.icons.checks.hud_picture('field',frame)['matched']:return result()
            top=self.icons.simple(frame,'event_button_top',(1004,509,1050,540),.82,False)
            bottom=self.icons.simple(frame,'event_button_bottom',(1007,549,1050,575),.82,False)
            aligned=abs(top['position'][0]-bottom['position'][0]+3)<=4 and abs(bottom['position'][1]-top['position'][1]-40)<=4
            return result(top['matched'] and bottom['matched'] and aligned,observation=dict(top=top,bottom=bottom),position=(1004,509),template_size=(46,66),match_source='supplemental_final_attack_button')
        if name.endswith('MORNING'):
            bounds=((615,71,665,112),(489,169,535,213),(745,166,791,213),(534,328,579,371),(702,328,749,371))
            checks=[self.icons.simple(frame,'morning_corner_'+str(i),b,.80,False) for i,b in enumerate(bounds)]
            count=sum(c['matched'] for c in checks)
            return result(count>=4,score=count/5.,threshold=.8,position=(494,76),template_size=(292,290),observation=checks,match_source='supplemental_morning_4_of_5')
        if name.endswith('NIGHT'):
            return clock_pentagon(frame,True)
        if name in ('POKEMON_ZA_FURADARI_MAP','POKEMON_ZA_UG_SEWER_MAP'):
            return self.other_map(frame)
        if name in ('POKEMON_ZA_MOVE_COMMENT_BATTLE','POKEMON_ZA_MOVE_COMMENT_BATTLE2'):
            match=self.stable('map-warning',self.map_warning(frame),command,3.0)
            return result(match,match_source='supplemental_map_warning_3s')
        if name in ('POKEMON_ZA_LOSE','POKEMON_ZA_FURADARI_EYES_DARK_COMMENT'):
            if getattr(command,'_za_mega_last_battle_mode',False):
                # The final victory also has a black narration screen. Its
                # dedicated MEGA retry/end flow owns the result, not LOSE.
                self.timers.pop('defeat',None)
                return result()
            black=np.mean(np.max(frame[:536,:912],2)<=24)>=.985
            # Same black-background gate as MEGA, plus completed comment and
            # no choice. Exclude the opening narration and unrelated scenes.
            states=[str(v) for k,v in vars(command).items() if k.endswith('current_state')]
            active=any(v in ('BATTLE_MOVE','QUASAR_BATTLE_LOOP','COMMON_BATTLE_RETURN','COMMON_FURADARI_MAP_BATTLE_RECOVERY') for v in states)
            flows=getattr(command,'_za_story_battle_flows',{})
            active=active or any(v in states and f.get('active_seen') for v,f in flows.items() if isinstance(f,dict))
            active=active or any('KARASUBA_69' in v or 'KARASUBA_95' in v or 'FURADARI' in v for v in states)
            matched=bool(active and black and self.black_comment(frame) and self.choices(frame) is None)
            return result(self.stable('defeat',matched,command,5.0),match_source='supplemental_black_defeat_5s')
        if name in ('POKEMON_ZA_BOX_MENU','POKEMON_ZA_SELECT_ALL'):
            menu=self.menu(frame,'box' if name.endswith('BOX_MENU') else 'filter')
            return result(menu is not None and menu['selected']==0,observation=menu,match_source='supplemental_menu_rows')
        return result()
