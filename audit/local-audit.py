"""Local CLI/algorithm evidence. Does not contact cloud APIs or read credentials."""
import asyncio
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hub import alerts, scenario
from hub.agent import Config, Event, Reasoner
from hub.act import VirtualHub, VirtualLamp
from hub.lamp import CsiFrame, parse_csi
from hub.replay import Recording, Writer
from hub.routine import Routine
from hub.run import Guardian, load_rooms
from hub.sense import BreathSensor

OUT = ROOT/'audit/local'
OUT.mkdir(exist_ok=True)
ENV = {k:v for k,v in os.environ.items() if k not in {'NEBIUS_API_KEY','GHOST_REASON_MODEL','GHOST_LOG_MODEL','GHOST_LLM_BASE_URL','TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_FROM','ALERT_PHONE','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}}
for key in set(os.environ)-set(ENV):
    os.environ.pop(key, None)
results=[]
commands=[]

def cmd(module, *args, ok=True):
    p=subprocess.run([sys.executable,'-m',module,*map(str,args)],cwd=ROOT,env=ENV,text=True,capture_output=True)
    commands.append({'command':[sys.executable,'-m',module,*map(str,args)],'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    assert (p.returncode==0)==ok, commands[-1]
    return p.stdout+p.stderr

def row(id, fn):
    if os.getenv('GHOST_AUDIT_PREP') and id in {'G98','G100','G101','G114','G115'}:
        return
    begin=len(commands)
    stream=io.StringIO()
    try:
        with contextlib.redirect_stdout(stream): note=fn()
        status='PASS'
    except Exception as e:
        status='FAIL'; note=f'{type(e).__name__}: {e}'
    log={'id':id,'status':status,'note':note or 'All explicit assertions passed.','console':stream.getvalue(),'network':[], 'commands':commands[begin:]}
    (OUT/f'{id}.json').write_text(json.dumps(log,indent=2))
    results.append({'id':id,'status':status,'note':log['note'],'log':f'audit/local/{id}.json'})
    (OUT/'results.json').write_text(json.dumps(results,indent=2))
    print(id,status,str(note or '')[:160],flush=True)
    lines=(ROOT/'AUDIT.md').read_text().splitlines()
    for i,line in enumerate(lines):
        if line.startswith(f'| {id} |'):
            cols=[c.strip() for c in line.split('|')[1:-1]];cols[3]=status;cols[4]=f'[local commands/assertions](audit/local/{id}.json)';lines[i]='| '+' | '.join(cols)+' |'
    (ROOT/'AUDIT.md').write_text('\n'.join(lines)+'\n')

with tempfile.TemporaryDirectory(prefix='ghost-audit-') as temp:
    tmp=Path(temp)
    recording=scenario.ensure_night()
    rec=Recording.load(recording)
    routine=scenario.build_routine(rec.scene_start)
    routinefile=tmp/'routine.json';routine.save(routinefile)
    def cli_help():
        for module in ('hub.server','hub.run','hub.replay','hub.demo_3am','hub.fake_lamp'):
            text=cmd(module,'--help');assert 'usage:' in text
            assert 'usage:' in cmd(module,'--not-a-real-option',ok=False)
        text=commands[0]['stdout'];assert all('--'+x in text for x in ['host','port','recording','live','lamp','lamp-port','speed','reply'])
    row('G84',cli_help)
    def corrupt():
        import gzip
        for name,data in [('invalid',b'badgzip'),('magic',gzip.compress(b'wrong\n{}\n')),('record',gzip.compress(b'GHOSTCSI1\n{}\n\0'))]:
            file=tmp/(name+'.ghostcsi');file.write_bytes(data);cmd('hub.replay','info',file,ok=False)
        cmd('hub.replay','info',tmp/'missing.ghostcsi',ok=False)
    row('G86',corrupt)
    def info():
        before=hashlib.sha256(recording.read_bytes()).hexdigest()
        text=cmd('hub.replay','info',recording)
        assert str(len(rec.frames))+' frames' in text
        assert all(room in text for room in rec.rooms)
        assert '"synthetic": true' in text and '"scale": 20' in text
        assert hashlib.sha256(recording.read_bytes()).hexdigest()==before
    row('G89',info)
    def roundtrip():
        file=tmp/'roundtrip.ghostcsi';header={'scene_start':100,'scale':2,'synthetic':True,'markers':[{'t':1,'label':'format test'}]}
        w=Writer(file,header);expected=[(.5,'bedroom',500,-50,b'123'),(.7,'bathroom',700,-60,b'45')]
        for args in expected:w.frame(*args)
        w.close();r=Recording.load(file);assert r.header==header
        assert [(t,f.source,f.lamp_ms,f.rssi,f.amp) for t,f in r.frames]==expected
        assert r.duration==.7 and r.rooms==['bedroom','bathroom']
        assert all(a[0]<=b[0] for a,b in zip(rec.frames,rec.frames[1:]))
    row('G90',roundtrip)
    def scenario_cli():
        text=cmd('hub.scenario');r=Recording.load(scenario.RECORDING)
        assert r.header['synthetic'] is True and r.scale==20 and r.header['jump_to']==36
        assert len(r.header['markers'])==4 and set(r.rooms)==set(scenario.SENSED)
        assert str(scenario.RECORDING) in text and 'bedroom' in text
    row('G91',scenario_cli)
    def fit():
        text=cmd('hub.routine','fit',routinefile)
        actual=Routine.load(routinefile);actual.fit();assert f'fit {routinefile}: {actual.nights} days, rooms' in text
        assert all(room in text for room in routine.model)
        assert Routine.load(routinefile).minutes
    row('G92',fit)
    def show():
        before=routinefile.read_bytes();text=cmd('hub.routine','show',routinefile,'bathroom')
        assert len([l for l in text.splitlines() if l[:2].isdigit() and l[2:3]==':'])==48
        assert 'bathroom occupied at' in text and routinefile.read_bytes()==before
    row('G93',show)
    def invalid_routine():
        bad=tmp/'bad.json';bad.write_text('{invalid');original=bad.read_bytes()
        for args in [(),('fit',),('fit',tmp/'absent'),('fit',bad),('show',routinefile,'unknown')]:
            text=cmd('hub.routine',*args,ok=False);assert 'error:' in text
        assert bad.read_bytes()==original
        empty=tmp/'empty.json';Routine().save(empty)
        assert '0 days, rooms []' in cmd('hub.routine','fit',empty)
    row('G94',invalid_routine)
    def persistence():
        r=Routine.from_json(routine.to_json());r.fit(before=rec.scene_start)
        ref=list(r.model['bathroom'].baseline)
        for i in range(30):r.observe(rec.scene_start+i*60,'bathroom',True)
        assert r.model['bathroom'].baseline==ref
        file=tmp/'persist.json';r.save(file);loaded=Routine.load(file)
        assert loaded.to_json()==r.to_json()
        loaded.fit(before=rec.scene_start);assert loaded.model['bathroom'].baseline==ref
        loaded.fit(before=rec.scene_start+86400);assert loaded.model['bathroom'].baseline!=ref
        assert set(r.to_json()['minutes']['bathroom'].values().__iter__().__next__())<=set('.01')
    row('G95',persistence)
    def dwell():
        normal=routine.dwell_score('bathroom',rec.scene_start,240)
        long=routine.dwell_score('bathroom',rec.scene_start,720)
        assert not normal['anomalous'] and long['anomalous']
        r=Routine();assert not r.dwell_score('bathroom',rec.scene_start,720)['anomalous']
        assert r.presence_score('bathroom',rec.scene_start,True)['p'] is None
    row('G96',dwell)
    def docs_routine():
        readme=(ROOT/'README.md').read_text();submission=(ROOT/'SUBMISSION.md').read_text()
        assert 'Local JSON operations' in readme and 'planned/optional' in readme and 'no cloud job runs' in readme
        assert 'Optional, for the Serverless story' in submission
    row('G97',docs_routine)
    def rooms():
        missing=tmp/'missing-rooms.json';assert load_rooms(missing)=={'lamp':{'pan':0}}
        file=tmp/'rooms.json';data={'bedroom':{'pan':-47,'sleep':True}}
        for j in [data,{'rooms':data}]:file.write_text(json.dumps(j));assert load_rooms(file)==data
        os.environ['GHOST_ROOMS']=str(file)
        assert load_rooms()==data;os.environ.pop('GHOST_ROOMS')
        g=Guardian(VirtualHub(),Config(),data,Reasoner(),None,live_csi=False)
        assert 'bedroom' in g.cfg.sleep_rooms and g.followed_room() is None
    row('G99',rooms)
    # Each pytest selection executes the named local contract; model-mocked tests are not used as cloud proof.
    testmap={
      'G103':['tests/test_act.py::test_plans','tests/test_act.py::test_plans_never_hand_out_the_shared_templates'],
      'G104':['tests/test_agent.py::test_got_up_then_too_still','tests/test_agent.py::test_got_up_then_settles_back_to_sleep','tests/test_agent.py::test_daytime_motion_is_not_getting_up'],
      'G105':['tests/test_rules_rooms.py::test_the_watch_follows_the_person_into_another_room','tests/test_rules_rooms.py::test_a_still_person_stays_present_until_seen_elsewhere','tests/test_agent.py::test_breath_gone_after_walking_out_is_not_an_alarm'],
      'G106':['tests/test_rules_rooms.py::test_jolt_then_stillness_is_a_possible_fall','tests/test_rules_rooms.py::test_walking_is_not_a_fall_and_sleep_rooms_are_exempt','tests/test_agent.py::test_fallen_but_breathing_outside_the_bedroom_still_checks_in','tests/test_routine.py::test_long_stay_uses_the_learned_routine'],
      'G107':['tests/test_agent.py::test_breath_lost_without_motion','tests/test_rules_rooms.py::test_a_flicker_of_breathing_in_an_empty_room_is_not_breath_lost','tests/test_agent.py::test_breath_gone_after_walking_out_is_not_an_alarm'],
      'G108':['tests/test_audit_contracts.py::test_decision_queue_recovers_after_invalid_event','tests/test_replay.py::test_the_3am_night_end_to_end'],
      'G109':['tests/test_evidence.py::test_cite_strips_invented_ids_and_keeps_real_ones','tests/test_evidence.py::test_cite_adds_citations_when_the_model_gave_none','tests/test_evidence.py::test_cite_honours_the_cites_list','tests/test_evidence.py::test_rules_only_explanations_cite_too','tests/test_evidence.py::test_witness_writes_numbers_from_the_readings'],
      'G111':['tests/test_hub.py::test_breathing_rate','tests/test_hub.py::test_empty_room_has_no_confident_breathing','tests/test_hub.py::test_walking_raises_motion_and_suppresses_rate','tests/test_audit_contracts.py::test_sensor_warmup_is_waiting_instead_of_invented_empty'],
      'G113':['tests/test_hub.py::test_parse_csi_roundtrip','tests/test_audit_contracts.py::test_truncated_csi_does_not_yield_a_partial_frame'],
      'G114':['tests/test_hub.py::test_link_hello_commands_and_csi'],
      'G115':['tests/test_act.py','tests/test_hub.py::test_ask_voice_answer','tests/test_hub.py::test_ask_button_answer','tests/test_hub.py::test_ask_no_answer'],
    }
    for id,tests in testmap.items():
        row(id,lambda tests=tests:cmd('pytest','-q',*tests))
    def incomplete():
        async def go():
            reasoner=Reasoner();assert not reasoner.online
            for kind in ['got_up','long_stay','no_answer','moved','answered']:
                d=await reasoner.decide(Event(kind,'bathroom','watch',{},rec.scene_start))
                assert d.by=='rules' and d.explain
            assert await reasoner.summarize({})=='no readings'
        asyncio.run(go())
    row('G110',incomplete)
    def irregular():
        s=BreathSensor();s.add(CsiFrame(1000,-50,b'1234567'));assert not s.buf
        for _,f in rec.frames:
            if f.source=='bedroom':s.add(f)
        assert s.read() is not None
        assert len(s.trace)<=100 and all(-1<=v<=1 for v in s.trace)
        old=len(s.buf);s.add(CsiFrame(1000,-50,bytes(range(32))));assert len(s.buf)<old
        assert s.read() is None
    row('G112',irregular)
    def printed():
        async def go():
            assert await alerts.call('GHOST audit printed-only probe')=='printed'
            assert await alerts.text('GHOST audit printed-only probe')=='printed'
        asyncio.run(go())
    row('G118',printed)
    def firmware_docs():
        files=list((ROOT/'firmware/hotaru-ghost').glob('*'))
        assert files and not any(f.suffix=='.ino' for f in files)
        text=(ROOT/'hub/README.md').read_text()+(ROOT/'README.md').read_text()+(ROOT/'SUBMISSION.md').read_text()
        assert not any(term in text for term in ['Magpie','Parakeet','Whisper','WebSocket'])
        assert 'TCP' in text and 'UDP' in text
    row('G129',firmware_docs)
    def build():
        p=subprocess.run(['npm','run','build'],cwd=ROOT/'web',capture_output=True,text=True,env=ENV)
        commands.append({'command':['npm','run','build'],'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        assert p.returncode==0
        config=(ROOT/'web/vite.config.ts').read_text();assert '5178' in config and '127.0.0.1:8780' in config and 'base: "./"' in config
    row('G130',build)
    def dependencies():
        deps=(ROOT/'requirements.txt').read_text();assert all(x in deps for x in ['numpy','scipy','httpx','pytest'])
        ini=(ROOT/'pytest.ini').read_text();assert 'testpaths = tests' in ini and 'pythonpath = .' in ini
        return cmd('pytest','--collect-only','-q')
    row('G131',dependencies)
    def absent_surface(kind):
        names=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['node_modules','.venv','.git','.loom','audit','dist','__pycache__','.pytest_cache'])]
        if kind=='mcp':assert not any('mcp' in n.lower() for n in names)
        else:assert not any(Path(n).suffix in ['.sol','.ak','.plutus','.cairo'] for n in names)
        return 'Inspected repository inventory: '+str(len(names))+' source/document files; no '+kind+' implementation.'
    row('G132',lambda:absent_surface('mcp'))
    row('G133',lambda:absent_surface('contract'))
    def honesty():
        text=(ROOT/'README.md').read_text()+(ROOT/'SUBMISSION.md').read_text()
        assert 'synthe' in text.lower() and 'possible fall' in text.lower()
        assert 'planned' in text and 'Setup required: NEBIUS_API_KEY' in text
        assert 'Setup required: NEBIUS_API_KEY' in (ROOT/'web/src/components/BrandPlate.tsx').read_text()
    row('G134',honesty)
    def headless():
        p=subprocess.Popen([sys.executable,'-m','hub.run','--port','39770'],cwd=ROOT,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        try:
            time.sleep(2)
        finally:
            p.terminate();text=p.communicate(timeout=5)[0]
        commands.append({'command':['python','-m','hub.run','--port','39770'],'pid':p.pid,'exit':p.returncode,'stdout':text})
        assert 'rules only' in text and 'real timings' in text and 'no readings' in text
        assert 'tcp 39770' in text and 'udp 39771' in text
        p=subprocess.Popen([sys.executable,'-m','hub.run','--demo','--port','39772','--follow',''],cwd=ROOT,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        try:time.sleep(2)
        finally:p.terminate();text=p.communicate(timeout=5)[0]
        commands.append({'command':['python','-m','hub.run','--demo','--port','39772','--follow',''],'pid':p.pid,'exit':p.returncode,'stdout':text})
        assert 'demo timings' in text and 'no readings' in text
    row('G98',headless)
    def headless_persistence():
        file=ROOT/'data/live/routine.json';assert file.exists()
        r=Routine.load(file);assert not r.minutes and not r.visits
        text=(ROOT/'hub/run.py').read_text()
        assert 'routine.save(path)' in text and 'now - last_save > 600' in text
        assert 'today.tm_yday != fitted_day' in text and 'routine.fit(before=now)' in text
        assert 'Routine.load(routine_path) if routine_path.exists()' in text
        file.unlink()
        return cmd('pytest','-q','tests/test_audit_contracts.py::test_headless_calendar_maintenance_uses_real_persisted_history')
    row('G100',headless_persistence)
    def fake_cli():
        text=cmd('hub.fake_lamp','--help');assert all(x in text for x in ['--hub','--port','--bpm','--reply'])
        source=(ROOT/'hub/fake_lamp.py').read_text()
        assert 'fake-hotaru' in source and 'hotaru3-ghost' in source and 'synthetic Wi-Fi CSI' in source
        assert 'range(30)' in source
        return cmd('pytest','-q','tests/test_hub.py::test_link_hello_commands_and_csi','tests/test_hub.py::test_ask_voice_answer')
    row('G101',fake_cli)
    def demo_source():
        text=cmd('hub.demo_3am','--help');assert '--auto' in text and '--port' in text
        source=(ROOT/'hub/demo_3am.py').read_text()
        assert source.index('lamp.eye("follow"')<source.index('lamp.eye("path"')<source.index('lamp.eye("amber"')<source.index('lamp.ask(')
        assert 'lamp.eye("red")' in source and 'lamp.action("nod"' in source and 'alerts.call(msg)' in source
        assert 'sys.stdin.readline' in source and 'asyncio.sleep(seconds)' in source and 'await hub.close()' in source
        return 'Entry/help and source sequence inspected only; physical demonstration remains G127 UNTESTED.'
    row('G102',demo_source)
