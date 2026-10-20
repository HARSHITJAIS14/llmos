"""Six visually inspected perception cases. No API calls or model judgments."""
import json
import random
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'screen_understanding/providers/runs/perception-ablation-01'


def main():
    cases=[]
    rng=random.Random(39)
    def add(sid,questions,ground):
        w,h=Image.open(OUT/'images'/f'{sid}.png').size
        qs={}; truth={}
        for i,(text,correct,wrong) in enumerate(questions):
            values=[correct]+wrong; rng.shuffle(values)
            criteria={f'o{j}':v for j,v in enumerate(values)}; key=f'q{i+1}'
            qs[key]=dict(type='choice',instructions=text+' in the screenshot in `image`.',criteria=criteria)
            truth[key]=dict(type='choice',choice=next(k for k,v in criteria.items() if v==correct))
        for i,(text,bbox) in enumerate(ground):
            key=f'g{i+1}';qs[key]=dict(type='box',instructions=text+' in the screenshot in `image`.')
            truth[key]=dict(type='box',bbox=[bbox[0]/w,bbox[1]/h,bbox[2]/w,bbox[3]/h])
        cases.append(dict(screen=sid,image=f'images/{sid}.png',size=[w,h],questions=qs,truth=truth,
                          reference_method='Manually inspected submitted screenshot; reference boxes in submitted-image coordinates'))
    add('screen_0001',[
        ('Which appearance theme is selected','Dark',['Auto','Light','No selection']),
        ('Which Liquid Glass option is selected','Clear',['Tinted','Both','Neither']),
        ('Which Show scroll bars radio option is selected','Automatically based on mouse or trackpad',['When scrolling','Always','None']),
        ('What is the sidebar item immediately below Appearance','Apple Intelligence & Siri',['Desktop & Dock','Appearance tab','General']),
        ('What does the green circular window control at upper left normally do','Maximize or enter full screen',['Close window','Minimize window','Change theme']),
        ('Which icon and widget style is selected','Default',['Dark','Clear','Tinted'])],
        [('The Apple Intelligence & Siri sidebar row',[35,834,414,892]),('The green circular window control at upper left',[126,35,155,67])])
    add('screen_0041',[
        ('What is the title at the top of the main pane','Screen Time',['Screw Time','Appearance','Communication Safety']),
        ('What is the first row under Limit Usage','Downtime',['App Limits','Screen Distance','Always Allowed']),
        ('Which sidebar category is visibly selected','Screen Time',['Focus','Appearance','Privacy & Security']),
        ('Which row immediately follows App Limits','Always Allowed',['Screen Distance','Downtime','Notifications']),
        ('What is displayed in the Activity section','App & Website Activity, Notifications, and Pickups rows',['A populated weekly usage bar chart','Only a blank page','A list of Bluetooth devices']),
        ('Which of these belongs in the Communication section','Communication Safety',['Screen Distance','Content & Privacy','App Limits'])],
        [('The App Limits row in the main pane',[486,684,1370,786]),('The Screen Distance row in the main pane',[486,887,1370,987])])
    add('screen_0032',[
        ('Which settings page is open in the foreground window','Bluetooth',['Privacy & Security','Network','General']),
        ('Is the Bluetooth toggle visually on or off','On',['Off','Toggle absent','Cannot determine']),
        ('What connection status is shown for Airdopes 800','Not Connected',['Connected','Pairing','No status displayed']),
        ('What does the stacked preview on the left with a month grid depict','Calendar app preview',['The foreground Bluetooth panel','A search field','A file list']),
        ('What temperature is shown in the Varanasi weather widget','31 degrees',['23 degrees','69 degrees','13 degrees']),
        ('Which app is in the foreground','System Settings',['Calendar','Weather','Finder'])],
        [('The Calendar app preview with a month grid on the left side of the desktop',[12,382,141,504]),
         ('The blue Bluetooth on/off toggle at the upper right of the foreground settings pane',[1214,161,1268,189])])
    add('screen_0057',[
        ('Which application is shown','Finder',['System Settings','Terminal','Chrome']),
        ('Which folder is open','Applications',['Downloads','Documents','Desktop']),
        ('Which file view layout is visible','List with columns',['Icon grid','Gallery preview','Column browser']),
        ('Which column immediately follows Date Modified','Size',['Name','Kind','Tags']),
        ('What size is shown for Calendar','13.1 MB',['119.1 MB','6 MB','17.8 MB']),
        ('What is the function of the three-dot toolbar button near the top right','More options',['Search','Share','Change folder name'])],
        [('The search button with a magnifying glass at the top right',[1488,11,1564,78]),
         ('The Applications sidebar entry',[38,526,307,581])])
    add('screen_0171',[
        ('What is actually visible in the page viewport','Blank dark teal area',['A rendered Wikipedia article','Python standard library documentation','A GitHub pull request list']),
        ('Which tab is selected','Untitled',['The Python standard library','GitHub repository','Pull requests']),
        ('How many tabs are visible','Four',['Three','Five','Two']),
        ('Which site and page does the address bar reference','Wikipedia Python programming language',['Python standard library documentation','GitHub Spoon-Knife repository','Google search']),
        ('What does the X-shaped control immediately right of the forward arrow indicate','Stop loading the page',['Close the application','Open extensions','Reload completed page']),
        ('Which AI assistant name is written on the top-right button','Gemini',['ChatGPT','Claude','Copilot'])],
        [('The plus button for opening a new browser tab',[1310,10,1342,42]),
         ('The close icon on the active Untitled tab',[1265,11,1297,42])])
    add('screen_0342',[
        ('What kind of application is shown','Terminal shell',['Text editor','Web browser','Spreadsheet']),
        ('Why did the git status command fail','Current directory is not inside a Git repository',['Wrong password','Network disconnected','Merge conflict']),
        ('What is the most recent executed command','uptime',['git status','pwd','ls']),
        ('Which directory is indicated by the shell prompt','~/Desktop/YC',['~/Downloads','/tmp','/data/harshitj23']),
        ('What is the first displayed load average','7.77',['4.69','3.00','20.30']),
        ('What state is the shell in at the bottom','Waiting for input at a fresh prompt',['Still running git status','Asking for a password','Showing an editor buffer'])],
        [('The plus button for opening a new Terminal tab near the top right',[1519,40,1563,80]),
         ('The fatal not a git repository error text line',[10,213,904,250])])
    (OUT/'cases.json').write_text(json.dumps(cases,indent=2))
    print('Prepared',len(cases),'screens,',sum(len(c['questions']) for c in cases),'perception tasks.')


if __name__=='__main__':main()
