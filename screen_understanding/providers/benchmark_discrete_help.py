"""Two-request/provider diagnostic: numbered regions, with/without short labels."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import time
from dotenv import dotenv_values
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from benchmark_jev import API,make_body
from benchmark_perception_help import RULES


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--env',type=Path,required=True);a=p.parse_args()
    out=a.run/'discrete';out.mkdir(exist_ok=False)
    hints=json.loads((a.run/'student_boxes.json').read_text())['screen_0032'];hints={h['id']:h for h in hints}
    selected=[('d_0001','The selected Bluetooth row in the settings sidebar'),
              ('d_0004','The search field in the settings sidebar'),
              ('d_0058','The blue Bluetooth on/off toggle'),
              ('d_0073','The Calendar app preview with a month grid on the far left of the desktop'),
              ('d_0048','The back and forward navigation arrows at the top of the foreground window'),
              ('d_0043','The Airdopes 800 device row'),
              ('d_0002','The Varanasi weather widget showing 31 degrees'),
              ('d_0066','The Learn more link in the Bluetooth explanation')]
    random.Random(9).shuffle(selected)
    image=Image.open(a.run/'images/screen_0032.png').convert('RGB');draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
    questions={};truth={};aux=[]
    criteria={f'b{i+1}':f'Numbered region {i+1}' for i in range(8)}
    for i,(source,description) in enumerate(selected):
        h=hints[source];l,t,r,b=[v*s for v,s in zip(h['bbox'],[image.width,image.height,image.width,image.height])]
        draw.rectangle([l,t,r,b],outline='#ff3232',width=2)
        label=str(i+1);yy=max(0,t-21)
        draw.rectangle([l,yy,l+25,yy+21],fill='#ff3232');draw.text((l+4,yy),label,font=font,fill='white')
        key=f'q{i+1}';questions[key]=dict(type='choice',instructions='Which numbered region corresponds to '+description+' in `image`? Return its region choice.',criteria=criteria)
        truth[key]=f'b{i+1}';aux.append(dict(id=f'b{i+1}',bbox=h['bbox'],label=h['label']))
    image.save(out/'numbered.png')
    (out/'case.json').write_text(json.dumps(dict(questions=questions,truth=truth,auxiliary_boxes=aux,
       note='Same numbered image in both arms. Raw detector boxes, actual student labels; questions/references visually checked. Extra metadata is optional.'),indent=2))
    keys=dotenv_values(a.env)
    original=[json.loads(l) for l in (a.run/'attempts.jsonl').read_text().splitlines()]
    def worker(provider,key_name,index):
        assert sum(r['provider']==provider for r in original)<=18
        key=keys[key_name]
        client=API(key,'direct') if provider.startswith('jev') else genai.Client(api_key=key,http_options={'timeout':60000,'retry_options':{'attempts':1}})
        for condition in (['numbered','numbered_labels'] if index%2==0 else ['numbered_labels','numbered']):
            dest=out/f'{provider}_{condition}.json'
            prompt=RULES+'\nQuestions: '+json.dumps(questions)
            if condition=='numbered_labels':prompt+='\nAuxiliary imperfect region predictions (bbox normalized xyxy): '+json.dumps(aux)
            row=dict(provider=provider,condition=condition)
            try:
                start=time.perf_counter()
                if provider.startswith('jev'):
                    body=make_body(provider,image,questions,'direct');body['state']['rules']=RULES
                    if condition=='numbered_labels':body['state']['auxiliary_boxes']=aux
                    result=client.call(body)
                    if result.get('error'):raise RuntimeError(json.dumps(result['error']))
                    answers={k:v.get('choice') for k,v in result['response'].get('answers',{}).items()}
                    row['usage']=result['response'].get('usage',{});row['raw_response']=result['response']
                else:
                    schema=dict(type='object',properties={k:dict(type='string',enum=list(criteria)) for k in questions},required=list(questions))
                    response=client.models.generate_content(model=provider,contents=[image,prompt],config=types.GenerateContentConfig(
                        temperature=0,response_mime_type='application/json',response_json_schema=schema,max_output_tokens=1024))
                    answers=json.loads(response.text);row['usage']=response.usage_metadata.model_dump(mode='json')
                row.update(seconds=time.perf_counter()-start,answers=answers,correct=sum(answers.get(k)==v for k,v in truth.items()),total=len(truth))
            except Exception as exc:
                message=str(exc)
                for secret in keys.values():
                    if secret:message=message.replace(secret,'[REDACTED]')
                row['error']=message[:1200]
            dest.write_text(json.dumps(row,indent=2)); print(json.dumps({k:v for k,v in row.items() if k not in ['raw_response','usage','answers']}),flush=True)
            if row.get('error'):break
            time.sleep(5.5)
    providers=[('gemini-3.1-flash-lite','GEMINI_API_KEY'),('gemini-3.5-flash-lite','GOOGLE_API_KEY'),('jev-1.14.0','TYPESAFE_API_KEY')]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(worker,*provider,i) for i,provider in enumerate(providers)]
        for f in futures:f.result()


if __name__=='__main__':main()
