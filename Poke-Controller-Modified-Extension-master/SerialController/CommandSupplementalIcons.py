"""Non-text alternatives for the native, opt-in ZA Story run.

Assets are crops of the supplied Japanese references / ZIP frames. They are
not localized labels. Name AND original reference are checked by the caller.
"""
import time
import cv2
import numpy as np
try:
    from .CommandSupplementalScenes import SceneChecks, REFERENCES as SCENE_REFERENCES
except ImportError:
    from CommandSupplementalScenes import SceneChecks, REFERENCES as SCENE_REFERENCES


ICON_REFERENCES = {
    'POKEMON_ZA_X_MENU_OPEN': 'x_menu_window.png',
    'POKEMON_ZA_BOX_WINDOW': 'boxwindow.png',
    'POKEMON_ZA_ITEM_WINDOW': 'itemwindow.png',
    'POKEMON_ZA_MAP': 'map2.png',
    'POKEMON_ZA_MAP2': 'map2.png',
    'POKEMON_ZA_MOVESPOT_TAB': 'movespot_tab.png',
    'POKEMON_ZA_ZA_ROYALE': 'z-a_royale.png',
    'POKEMON_ZA_BATTLE_ACTIVE_LEVEL': 'battle_active_level.png',
    'POKEMON_ZA_PROFILE': 'Profile.png',
    'POKEMON_ZA_STARTBTN_SELECT': 'startbutton_select.png',
    'POKEMON_ZA_AME_S': 'ame_s.png',
    'POKEMON_ZA_WATER_ICON': 'water_icon.png',
    'POKEMON_ZA_REIBI_SKILL': 'reibi_skill.png',
    'POKEMON_ZA_REWARD_RESULT': 'REWARD.png',
    'POKEMON_ZA_CHICKET_MAX_RIGHT': 'chicket_95_118x1122_1268.png',
    'POKEMON_ZA_CHICKET_MAX': 'chicket_max.png',
    'POKEMON_ZA_FIN': 'fin.png',
    'POKEMON_ZA_MOVE_COMMENT': 'move_comment.png',
    'POKEMON_ZA_EVOLUTION_CONFIRM': 'evolution_2_select.png',
}
ASSETS = 'Template/ZA_Story_PIC/Supplemental/'
ICON_REFERENCES.update(SCENE_REFERENCES)


def white(frame):
    lo=frame.min(axis=2);hi=frame.max(axis=2)
    return ((lo>=180)&(hi.astype(np.int16)-lo<=45)).astype(np.uint8)*255


def choice_rows(frame):
    """Count the fixed right-side 2/3/4-choice rows, including the cursor row.

    Detect the highlighted rectangle separately from the dark rows. Map
    preview cards can touch the menu, so joining the entire panel is unsafe.
    Callers must additionally establish their map/evolution/defeat context.
    """
    mask=white(frame[280:550,900:1220])
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    found=[]
    for c in cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)[-2]:
        x,y,w,h=cv2.boundingRect(c);x+=900;y+=280
        if not (140<=w<=310 and 38<=h<=55):continue
        center=y+h/2
        def navy(cy):
            a=frame[int(cy)-12:int(cy)+12,x+15:x+w-15].astype(np.int16)
            return a.size>0 and np.mean((a[:,:,0]-a[:,:,2]>=12)&(a[:,:,0]>=35)&(a[:,:,0]<=165)&(a[:,:,1]<140))>.68
        for rows in (2,3,4):
            top=458-(rows-2)*52
            selected=round((center-top)/52)
            if not (0<=selected<rows and abs(center-(top+selected*52))<=9):continue
            if not all(i==selected or navy(top+i*52) for i in range(rows)):continue
            if navy(top-52) or navy(top+rows*52):continue
            found.append(dict(rows=rows,selected=selected,bounds=(x-5,int(top-29),w+10,rows*52+8)))
    return found[0] if len(found)==1 else None


class IconChecks:
    def __init__(self, checks):
        self.checks=checks
        self.fin_since=None
        self.scenes=SceneChecks(self,choice_rows)

    def score(self, frame, asset, bounds, gray=True):
        return self.checks.glyph(ASSETS+asset+'.png',frame,bounds,gray=gray)

    def simple(self, frame, asset, bounds, threshold=.9, gray=True):
        score,pos=self.score(frame,asset,bounds,gray)
        im=self.checks.images[(ASSETS+asset+'.png',gray)]
        return dict(matched=score>=threshold,score=score,threshold=threshold,
                    position=pos,template_size=(im.shape[1],im.shape[0]),
                    search_crop=bounds,template_path=ASSETS+asset+'.png',
                    match_source='supplemental_icon')

    def map_menu(self, frame):
        if not (self.simple(frame,'map_compass',(20,0,200,70))['matched']
                or self.scenes.other_map(frame)['matched']):
            return None
        return choice_rows(frame)

    @staticmethod
    def item_row(frame):
        found=[]
        for row in range(7):
            y=157+row*72
            # White selected bar and its green arrow, not a visible item below it.
            a=frame[y+8:y+55,330:410]
            arrow=cv2.cvtColor(frame[y+8:y+55,40:78],cv2.COLOR_BGR2HSV)
            if np.mean(white(a)>0)>.90 and cv2.countNonZero(cv2.inRange(arrow,(30,100,130),(85,255,255)))>=80:
                found.append(row)
        return found[0] if len(found)==1 else None

    def match(self, name, frame, command):
        no=dict(matched=False,score=0.0,threshold=1.0,position=(0,0),
                template_size=(1,1),match_source='supplemental_icon')
        if frame is None or frame.shape!=(720,1280,3):return no
        if name in SCENE_REFERENCES:return self.scenes.match(name,frame,command)
        simple={
            'POKEMON_ZA_X_MENU_OPEN':('menu_lines',(40,40,155,120)),
            'POKEMON_ZA_BOX_WINDOW':('box_cube',(35,0,130,75)),
            'POKEMON_ZA_ITEM_WINDOW':('item_bag',(0,0,85,85)),
            'POKEMON_ZA_MOVESPOT_TAB':('movespot',(20,110,95,170)),
            'POKEMON_ZA_ZA_ROYALE':('royale_emblem',(10,25,110,100)),
            'POKEMON_ZA_PROFILE':('profile_tick',(120,520,500,610)),
            'POKEMON_ZA_STARTBTN_SELECT':('profile_tick',(120,520,500,610)),
        }
        if name in simple:return self.simple(frame,*simple[name])
        if name in ('POKEMON_ZA_MAP','POKEMON_ZA_MAP2'):
            return self.simple(frame,'map_compass',(20,0,200,70))
        if name=='POKEMON_ZA_BATTLE_ACTIVE_LEVEL':
            candidates=[self.simple(frame,a,(205,515,265,565),.9,False) for a in ('male_symbol','female_symbol')]
            result=max(candidates,key=lambda a:a['score']);result['observation']=candidates
            return result
        if name in ('POKEMON_ZA_AME_S','POKEMON_ZA_WATER_ICON'):
            if not self.simple(frame,'item_bag',(0,0,85,85))['matched']:return no
            # The existing 30-row search changes this state to TARGET_SIDE
            # after its first miss, while continuing inside TARGET_HIGH.
            if name.endswith('AME_S') and getattr(command,'common_item_use_current_state','') not in ('COMMON_ITEM_USE_TARGET_HIGH','COMMON_ITEM_USE_TARGET_SIDE'):return no
            if name.endswith('WATER_ICON') and getattr(command,'_6_story_current_state','')!='6_STORY_YUKARI_48':return no
            row=self.item_row(frame)
            if row is None:return no
            bounds=(78,169+row*72,122,211+row*72)
            result=self.simple(frame,'candy_s' if name.endswith('AME_S') else 'water_bottle',bounds,.90,False)
            result['selected_row']=row
            if name.endswith('AME_S'):
                other,_=self.score(frame,'candy_xs',bounds,False)
                result['competitor_score']=other
                result['matched']=result['matched'] and result['score']-other>=.06
            return result
        if name=='POKEMON_ZA_REIBI_SKILL':
            # SHIRO_32: the TM tab has orange / cyan / gray discs. The ice
            # snowflake appears AFTER A and must not authorize the search A.
            if (getattr(command,'_4_story_current_state','')!='4_STORY_SHIRO_32'
                    or not getattr(command,'_za_common_skill_target_search_active',False)
                    or np.mean(white(frame[65:155,550:630])>0)<.85):return no
            if np.mean(white(frame[280:318,150:470])>0)<.90:return no
            # Confirm the three-item layout, its cyan disc and green cursor.
            # The two neighboring discs rule out a cyan learned-move symbol.
            orange=cv2.cvtColor(frame[234:266,75:101],cv2.COLOR_BGR2HSV)
            cyan=cv2.cvtColor(frame[286:318,75:101],cv2.COLOR_BGR2HSV)
            gray=frame[338:370,75:101]
            arrow=cv2.cvtColor(frame[275:326,45:78],cv2.COLOR_BGR2HSV)
            counts=(cv2.countNonZero(cv2.inRange(orange,(5,100,100),(28,255,255))),
                    cv2.countNonZero(cv2.inRange(cyan,(78,55,140),(105,255,255))),
                    int(np.count_nonzero(white(gray))),
                    cv2.countNonZero(cv2.inRange(arrow,(30,100,130),(85,255,255))))
            matched=counts[0]>=35 and counts[1]>=50 and counts[2]>=60 and counts[3]>=70
            return dict(no,matched=matched,score=1.0 if matched else 0.0,
                        position=(45,228),template_size=(475,150),observation=counts,
                        match_source='supplemental_tm_three_discs')
        if name=='POKEMON_ZA_REWARD_RESULT':
            arrows=self.simple(frame,'reward_arrows',(925,435,1035,550),.85)
            ticket=self.simple(frame,'reward_ticket',(700,610,790,690),.85)
            coin=self.simple(frame,'reward_coin',(1060,610,1140,690),.85)
            result=dict(arrows)
            result.update(matched=arrows['matched'] or (ticket['matched'] and coin['matched']),
                          observation=dict(arrows=arrows,ticket=ticket,coin=coin))
            if not arrows['matched'] and result['matched']:result.update(score=min(ticket['score'],coin['score']),position=(700,610),template_size=(440,80))
            return result
        if name in ('POKEMON_ZA_CHICKET_MAX_RIGHT','POKEMON_ZA_CHICKET_MAX'):
            # Only the strips above/below MAX. Require both, and the original
            # geometry; text length/content does not contribute to the score.
            right=name.endswith('_RIGHT')
            x,y,x2,y2=(1122,95,1268,118) if right else (778,634,944,660)
            hsv=cv2.cvtColor(frame[y:y2,x:x2],cv2.COLOR_BGR2HSV)
            # The result MAX uses a purple gradient; numeric totals have a
            # red/pink bar with hue about 163. Broad pink alone misclassifies it.
            pink=cv2.inRange(hsv,(125,105,110),(179 if right else 155,255,255))>0
            fractions=(float(np.mean(pink[:3])),float(np.mean(pink[-3:])))
            threshold=.30 if right else .60
            matched=min(fractions)>=threshold
            if not right:
                # Keep the original broad-strip coverage gate too. A sparse
                # purple patch cannot authorize a partially filled total.
                coverage=cv2.inRange(hsv,(125,105,110),(179,255,255))>0
                matched=matched and min(float(np.mean(coverage[:3])),float(np.mean(coverage[-3:])))>=.80
            if matched:
                if right:
                    matched=self.simple(frame,'max_right_ticket',(1070,85,1125,130),.90,False)['matched']
                else:
                    matched=self.match('POKEMON_ZA_REWARD_RESULT',frame,command)['matched']
            return dict(no,matched=matched,score=min(fractions),threshold=threshold,
                        position=(x,y),template_size=(x2-x,y2-y),observation=fractions,
                        match_source='supplemental_max_strips')
        if name=='POKEMON_ZA_MOVE_COMMENT':
            menu=self.map_menu(frame)
            if menu and menu['rows']==2 and menu['selected']==0:
                x,y,w,h=menu['bounds'];return dict(no,matched=True,score=1.0,position=(x,y),template_size=(w,h),observation=menu,match_source='supplemental_map_yes')
            return no
        if name=='POKEMON_ZA_EVOLUTION_CONFIRM':
            if getattr(command,'common_evolution_current_state','')!='COMMON_EVOLUTION_EXEC':return no
            menu=choice_rows(frame)
            if menu and menu['rows']==2 and menu['selected']==0:
                x,y,w,h=menu['bounds'];return dict(no,matched=True,score=1.0,position=(x,y),template_size=(w,h),observation=menu,match_source='supplemental_evolution_choice')
            return no
        if name=='POKEMON_ZA_FIN':
            if getattr(command,'_8_story_current_state','')!='8_STORY_STORY_LAST_51':
                self.fin_since=None;return no
            small=cv2.resize(frame,(320,180),interpolation=cv2.INTER_AREA)
            result=self.simple(small,'fin_flowers',(42,77,266,166),.90,False)
            if not result['matched']:
                self.fin_since=None;return result
            if self.fin_since is None:self.fin_since=time.monotonic()
            result['matched']=time.monotonic()-self.fin_since>=10.0
            result['position']=tuple(v*4 for v in result['position'])
            result['template_size']=tuple(v*4 for v in result['template_size'])
            result['match_source']='supplemental_fin_background_10s'
            return result
        return no
