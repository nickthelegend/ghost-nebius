import fs from 'node:fs';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import net from 'node:net';
import assert from 'node:assert/strict';
import { chromium } from '/tmp/ghost-browser-tools/node_modules/playwright/index.mjs';
const root=process.cwd(), out=path.join(root,'audit/browser');
fs.mkdirSync(out,{recursive:true});
for(const f of fs.readdirSync(out))fs.unlinkSync(path.join(out,f));
const env={...process.env};
for(const key of ['NEBIUS_API_KEY','GHOST_REASON_MODEL','GHOST_LOG_MODEL','GHOST_LLM_BASE_URL','TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_FROM','ALERT_PHONE','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID']) delete env[key];
const observerDir=fs.mkdtempSync('/tmp/ghost-audit-observer-');
fs.writeFileSync(path.join(out,'hub-network.jsonl'),'');
fs.writeFileSync(path.join(observerDir,'sitecustomize.py'),`import sys, json\ndef observe(event, args):\n    if event == "socket.connect":\n        with open(${JSON.stringify(path.join(out,'hub-network.jsonl'))}, "a") as f:\n            f.write(json.dumps({"event": event, "address": str(args[1])}) + "\\n")\nsys.addaudithook(observe)\n`);
env.PYTHONPATH=observerDir+(env.PYTHONPATH?':'+env.PYTHONPATH:'');
let hub,browserServer,browser,ctx,page,port,base;
const results=[], consoleLog=[], network=[], pageErrors=[], allSnapshots=[];
const intentionalClosures=new WeakSet();
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function free(p){return new Promise(resolve=>{const s=net.createServer();s.once('error',()=>resolve(false));s.listen(p,'127.0.0.1',()=>s.close(()=>resolve(true)));});}
const hubs=new Set();
async function start(args=[]){
  assert(!hub||hub.exitCode!==null||hub.signalCode!==null,'previous hub must be stopped before starting another');
  const child=spawn(path.join(root,'.venv/bin/python'),['-m','hub.server','--host','127.0.0.1','--port',String(port),...args],{cwd:root,env,stdio:['ignore','pipe','pipe']});
  hub=child;hubs.add(child);let startup='';
  const capture=data=>{fs.appendFileSync(path.join(out,'hub.log'),data);startup=(startup+data.toString()).slice(-16384);};
  child.stdout.on('data',capture);child.stderr.on('data',capture);
  fs.appendFileSync(path.join(out,'processes.log'),`hub PID ${child.pid} port ${port} args ${args.join(' ')}\n`);
  for(let i=0;i<150;i++){
    if(child.exitCode!==null||child.signalCode!==null)throw new Error(`hub PID ${child.pid} exited before listening`);
    if(startup.includes(`GHOST dashboard on http://127.0.0.1:${port}`)){const r=await fetch(base+'/api/state');assert(r.ok);return;}
    await wait(100);
  }
  throw new Error('hub startup timeout');
}
async function stopChild(child){
 if(child&&child.exitCode===null&&child.signalCode===null){const exited=new Promise(r=>child.once('exit',r));child.kill('SIGTERM');await exited;fs.appendFileSync(path.join(out,'processes.log'),`stopped hub PID ${child.pid}\n`);}
}
async function stop(){const child=hub;hub=null;await stopChild(child);}
let cleaning=false;
async function cleanup(){
 if(cleaning)return;cleaning=true;
 if(browser)await browser.close().catch(()=>{});
 if(browserServer){const pid=browserServer.process().pid;await browserServer.close().catch(()=>{});fs.appendFileSync(path.join(out,'processes.log'),`closed Chrome PID ${pid}\n`);}
 for(const child of hubs)await stopChild(child);hub=null;
 fs.rmSync(observerDir,{recursive:true,force:true});
}
for(const [signal,code] of [['SIGTERM',143],['SIGINT',130]])process.once(signal,async()=>{await cleanup();process.exit(code);});
process.once('unhandledRejection',async error=>{console.error(error);await cleanup();process.exit(1);});
async function observed(p){
  p.on('console',m=>consoleLog.push({type:m.type(),text:m.text(),url:p.url()}));
  p.on('pageerror',e=>pageErrors.push(String(e)));
  p.on('request',r=>network.push({event:'request',method:r.method(),url:r.url()}));
  p.on('response',r=>network.push({event:'response',status:r.status(),url:r.url(),type:r.headers()['content-type']}));
  p.on('requestfailed',r=>network.push({event:intentionalClosures.has(p)&&r.url().endsWith('/api/stream')&&r.failure()?.errorText==='net::ERR_ABORTED'?'expected-stream-close':'failed',url:r.url(),error:r.failure()?.errorText}));
  await p.addInitScript(()=>{
    window.audit={created:0,active:0,snapshot:null,seen:[]};
    const Native=window.EventSource;
    window.EventSource=class extends Native{
      constructor(...args){super(...args);window.audit.created++;window.audit.active++;this.auditClosed=false;this.addEventListener('message',e=>{const s=JSON.parse(e.data);window.audit.snapshot=s;window.audit.seen.push(s);if(window.audit.seen.length>500)window.audit.seen.shift();});}
      close(){if(!this.auditClosed){window.audit.active--;this.auditClosed=true;}super.close();}
    };
  });
  return p;
}
async function snap(p=page){return p.evaluate(()=>window.audit.snapshot);}
async function next(test,timeout=15000,p=page){await p.waitForFunction(test,null,{timeout});return snap(p);}
async function post(action){const r=await page.evaluate(async action=>{const r=await fetch('api/'+action,{method:'POST'});return {status:r.status,body:await r.text()};},action);return r;}
async function fresh(){await post('replay/restart');await next(()=>window.audit.snapshot?.replay.pos<1);}
async function jump(){await page.getByRole('button',{name:'Jump to just before he gets up',exact:true}).click();await next(()=>window.audit.snapshot?.replay.pos>=36&&window.audit.snapshot?.replay.pos<42);}
async function speed(x=4){await page.getByRole('button',{name:`${x}×`,exact:true}).click();await next(()=>window.audit.snapshot?.replay.speed===4);}
async function checkin(){await fresh();await jump();await speed();await next(()=>window.audit.snapshot?.lamp.state.checkin,30000);}
async function shot(id){const file=`${id}.webp`;await page.screenshot({path:path.join(out,file),type:'webp',quality:30,fullPage:true});assert(fs.statSync(path.join(out,file)).size<=200000,'screenshot exceeds 200KB');return 'audit/browser/'+file;}
async function row(id,fn,{expectedFault=false}={}){
 const c=consoleLog.length,n=network.length,e=pageErrors.length;
 let status='PASS',note='';try{note=(await fn())||'Assertions matched the expected result.';}catch(err){status='FAIL';note=err.stack||String(err);}
 await wait(60);
 const logs={id,status,note,console:consoleLog.slice(c),pageErrors:pageErrors.slice(e),network:network.slice(n),expectedFault};
 const errors=logs.console.filter(x=>x.type==='error'); const bad=logs.network.filter(x=>x.event==='failed'||(x.status>=400));
 const allowedStatus={G65:[404],G75:[400],G77:[409],G78:[404],G79:[404],G80:[405],G83:[404],G51:[404]}[id]||[];
 const transport=/net::ERR_(CONNECTION_REFUSED|CONNECTION_CLOSED|EMPTY_RESPONSE|INCOMPLETE_CHUNKED_ENCODING|ABORTED)/;
 const unexpectedNetwork=bad.filter(x=>!expectedFault||(x.event==='failed'?(!x.url.startsWith(base)||!transport.test(x.error||'')):!allowedStatus.includes(x.status)));
 const unexpectedConsole=errors.filter(x=>!expectedFault||(!transport.test(x.text)&&!allowedStatus.some(s=>x.text.includes('status of '+s))));
 if(logs.pageErrors.length||unexpectedConsole.length||unexpectedNetwork.length){status='FAIL';note+='; unexpected console/network/page error';logs.status=status;logs.note=note;}
 logs.unexpectedConsole=unexpectedConsole;logs.unexpectedNetwork=unexpectedNetwork;
 let screenshot;try{screenshot=await shot(id);}catch(err){status='FAIL';note+='; '+err.message;}
 logs.status=status;logs.note=note;fs.writeFileSync(path.join(out,`${id}.json`),JSON.stringify(logs,null,2));
 results.push({id,status,note,screenshot,log:`audit/browser/${id}.json`});
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
 let audit=fs.readFileSync(path.join(root,'AUDIT.md'),'utf8');
 const lines=audit.split('\n').map(line=>{if(!line.startsWith('| '+id+' |'))return line;const cols=line.split('|').slice(1,-1).map(c=>c.trim());cols[3]=status;cols[4]=`[screenshot](${screenshot}) · [console/network](${logs.id?`audit/browser/${id}.json`:''})`;return '| '+cols.join(' | ')+' |';});
 fs.writeFileSync(path.join(root,'AUDIT.md'),lines.join('\n'));
 console.log(id,status,status==='FAIL'?note.split('\n').slice(0,3).join(' '):note.slice(0,100));
 for(const extra of ctx.pages().filter(p=>p!==page)){intentionalClosures.add(extra);await extra.close();}
 if(status==='FAIL'&&!hub&&expectedFault){await start();intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>!!window.audit.snapshot);}
}
const has=async(text,scope=page)=>{await scope.waitForFunction(t=>document.body.textContent.includes(t),text,{timeout:5000});assert((await scope.locator('body').textContent()).includes(text),`missing ${text}`);};
try{
 port=await free(8780)?8780:await free(37880)?37880:37881;base=`http://127.0.0.1:${port}`;
 await start();
 browserServer=await chromium.launchServer({executablePath:'/Users/jaibajrang/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing',headless:true});
 fs.appendFileSync(path.join(out,'processes.log'),`Chrome PID ${browserServer.process().pid}\n`);
 browser=await chromium.connect(browserServer.wsEndpoint());ctx=await browser.newContext({viewport:{width:1440,height:1000},locale:'en-GB',timezoneId:'Asia/Kolkata'});page=await observed(await ctx.newPage());
 await row('G3',async()=>{
   let release;const gate=new Promise(r=>release=r);
   await page.route('**/api/stream',async r=>{await gate;await r.continue().catch(()=>{});});
   await page.goto(base);await has('Connecting to the GHOST hub…');await has('Start it, then this page fills in on its own.');await has('--:--:--');await stop();release();await page.unrouteAll({behavior:'wait'});await wait(200);
 },{expectedFault:true});
 await row('G4',async()=>{await start();await next(()=>!!window.audit.snapshot);assert.equal(await page.evaluate(()=>window.audit.active),1);await has('GHOST');},{expectedFault:true});
 await row('G1',async()=>{assert.equal((await snap()).mode,'replay');assert.equal((await snap()).lamp.kind,'virtual');await has('synthetic night');const html=await page.request.get(base);assert.equal(await html.text(),fs.readFileSync(path.join(root,'web/dist/index.html'),'utf8'));return JSON.stringify({url:base,browser:browser.version(),builtIndexMatch:true});});
 await fresh();await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);
 await row('G2',async()=>{const s=await snap();assert.equal(s.replay.speed,1);assert.equal(s.replay.scale,20);assert(Math.abs(s.replay.start-(s.now-s.replay.pos*20))<.11);assert.equal(new Date(s.replay.start*1000).getHours(),2);});
 await row('G6',async()=>{await has('CSI-4 home guardian · Wi-Fi sensing · no cameras');for(const x of ['Sense','Reason','Act'])await has(x);assert(await page.getByLabel('Scene time').isVisible());});
 await row('G7',async()=>{await has('No signal');await has('Virtual HOTARU');await post('replay/resume');await next(()=>Object.values(window.audit.snapshot.rooms).filter(r=>r.sensor!==false).every(r=>r.confidence!==null&&r.confidence!==undefined),15000);await has('4 channels');});
 await row('G8',async()=>{await has('Setup required: NEBIUS_API_KEY');assert.equal(await page.locator('.plate-lamp-value').nth(1).evaluate(e=>e.scrollWidth>e.clientWidth),false,'setup label clipped');const s=await snap();assert.equal(s.model.online,false);assert.equal(fs.readFileSync(path.join(out,'hub-network.jsonl'),'utf8'),'');assert.equal(network.filter(x=>x.url.includes('api.tokenfactory.nebius.com')).length,0);assert(s.timeline.every(c=>c.by==='rules'));return JSON.stringify({model:s.model,hubOutboundConnections:0,TokenFactoryRequests:0});});
 await row('G9',async()=>{await has('Replay · scene time ×20 · synthetic night');assert.equal(await page.getByLabel('Scene time').innerText(),(await snap()).clock);});
 await row('G10',async()=>{for(const n of ['Stop the replay','Restart the night from 02:50','Jump to just before he gets up','1×','2×','4×'])assert(await page.getByRole('button',{name:n,exact:true}).isVisible());assert.equal(await page.locator('.acq-truth .acq-mark').count(),4);assert(await page.locator('.acq-head').isVisible());await has('Truth');});
 await row('G11',async()=>{await page.getByRole('button',{name:'Stop the replay',exact:true}).click();await next(()=>window.audit.snapshot.replay.paused);const s=await snap();await wait(1100);assert.equal((await snap()).replay.pos,s.replay.pos);assert.equal((await snap()).clock,s.clock);await page.getByRole('button',{name:'Run the replay',exact:true}).click();await next(()=>!window.audit.snapshot.replay.paused);await wait(700);assert((await snap()).replay.pos>s.replay.pos);});
 await row('G12',async()=>{for(const x of [1,2,4]){const n=network.length;await page.getByRole('button',{name:`${x}×`,exact:true}).click();await next(new Function(`return window.audit.snapshot.replay.speed===${x}`));assert.equal(await page.locator('.speed [aria-pressed=true]').count(),1);assert.equal(network.slice(n).filter(r=>r.event==='request'&&r.method==='POST'&&r.url.endsWith(`/speed?x=${x}`)).length,1);const a=(await snap()).replay.pos;await wait(1100);const delta=(await snap()).replay.pos-a;assert(delta>x*.5&&delta<x*1.8);}});
 await row('G13',async()=>{await fresh();const s=await snap();assert.equal(s.replay.speed,1);assert(!s.replay.paused);assert.equal(s.timeline.length,0);assert.equal(s.log.length,0);assert(s.clock.startsWith('02:50'));});
 await row('G14',async()=>{await jump();let s=await snap();assert(s.replay.pos>=36&&s.replay.pos<42);assert(s.followed==='bedroom'&&s.lamp.state.eye==='follow');await fresh();await page.getByRole('button',{name:'Jump to 03:02, just before he gets up',exact:true}).click();await next(()=>window.audit.snapshot.replay.pos>=36);assert((await snap()).replay.pos<42);});
 await row('G15',async()=>{const s=await snap();assert.deepEqual(s.replay.markers.map(m=>m.t),[0,42,47,56]);assert.equal(s.timeline.length,0);assert.equal(await page.locator('.acq-truth [title]').count(),4);});
 await row('G17',async()=>{const s=await snap();assert.deepEqual(Object.values(s.home.rooms).map(r=>r.plan),[[0,0,38,34],[38,0,24,20],[38,20,24,14],[62,0,38,34],[0,34,100,26]]);assert.equal(await page.locator('.door').count(),5);assert.deepEqual(s.home.plan.lamp,[47,44]);assert.equal(await page.locator('.room-floor').count(),5);});
 await row('G18',async()=>{await fresh();await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);await has('Waiting');assert((await page.locator('#plan-desc').textContent()).includes('Hall: No sensor'));assert.equal((await snap()).rooms.hall.sensor,false);assert.equal(await page.locator('.trace').count(),4);});
 await row('G21',async()=>{for(const x of ['CH1','CH2','CH3','CH4','Bedroom','Bathroom','Kitchen','Living room','−20 s','2 s/div','now'])await has(x);assert.equal(await page.locator('canvas').count(),4);assert.equal(await page.locator('.trace-read').count(),4);});
 await row('G24',async()=>{await has('Armed: watching every room');assert.equal(await page.locator('.armed-rooms li').count(),4);assert.equal(await page.locator('.armed-rules li').count(),4);assert(await page.locator('.key-jump').isVisible());});
 await row('G31',async()=>{await has('output · virtual lamp');await has('Quiet. HOTARU speaks only when something needs a person.');await has('No commands yet: HOTARU follows the breathing until something happens.');for(const x of ['Ring','Turned','Doing'])await has(x);});
 await row('G33',async()=>{const b=page.getByRole('button',{name:"HOTARU's button (arms on a check-in)",exact:true});assert(await b.isDisabled());const n=network.length;await b.dispatchEvent('click');assert.equal(network.slice(n).filter(x=>x.method==='POST'&&x.url.endsWith('/lamp/tap')).length,0);});
 await row('G46',async()=>{assert.equal(await page.getByRole('region',{name:'Log',exact:true}).count(),0);await post('replay/resume');await next(()=>window.audit.snapshot.log.length>0,15000);await has('rules');assert(await page.locator('.log li').count()<=6);});
 await row('G43',async()=>{await has('mask test · learned vs last 24 h');await has('Learned from 14 days of presence alone, no labels.');assert.equal(await page.locator('.mask-row').count(),4);assert.equal((await snap()).routine.rooms.bedroom.baseline.length,48);});
 await row('G44',async()=>{const s=await snap();for(const [i,m] of Object.values(s.routine.rooms).entries()){const expected=m.today.filter((t,b)=>t!==null&&((t>0&&m.baseline[b]<.15)||(t===0&&m.baseline[b]>.85))).length;assert.equal(await page.locator('.mask-row').nth(i).locator('.mask-viol').count(),expected);assert.equal(await page.locator('.mask-row').nth(i).locator('.mask-live').count(),m.today.filter(t=>t>0).length);}assert.equal(await page.locator('.mask-now').first().getAttribute('x1'),'95.7');});
 await row('G47',async()=>{await has('MIT · ESP32 Wi-Fi CSI → Nemotron on Nebius Token Factory → HOTARU');await has('The bundled night and its 14-day routine are synthesized from the channel model until a real night is recorded.');});
 // Follow a real uninterrupted synthetic night, including its silent wall-clock check-in.
 await fresh();await jump();await speed();
 await row('G19',async()=>{await next(()=>window.audit.snapshot.followed==='bedroom'&&window.audit.snapshot.rooms.bedroom.state==='moving');assert.equal(await page.locator('.room.is-followed').count(),1);await next(()=>window.audit.snapshot.followed==='bathroom',15000);assert((await snap()).rooms.bathroom.present);});
 await row('G20',async()=>{await next(()=>window.audit.snapshot.rooms.bathroom.anomaly>=.2,12000);assert(await page.locator('.room-anom').count()>0);assert((await page.locator('.room-anom title').first().textContent()).startsWith('Routine anomaly '));assert((await page.locator('.hotaru-bearing').getAttribute('style')).includes('7deg'));});
 await row('G22',async()=>{await next(()=>window.audit.seen.some(s=>s.rooms.bathroom.jolt>=600),10000);const seen=await page.evaluate(()=>window.audit.seen);assert(seen.some(s=>Object.values(s.rooms).some(r=>r.state==='moving'&&!r.bpm)));assert(seen.every(s=>['kitchen','living'].every(n=>!s.rooms[n].bpm)));assert(seen.some(s=>s.rooms.bathroom.jolt>=600));assert(seen.some(s=>s.rooms.bedroom.motion>=3));});
 await row('G23',async()=>{const s=await snap();for(const r of Object.values(s.rooms))if(r.trace){assert(r.trace.length<=100);assert(r.trace.every(v=>Number.isFinite(v)&&Math.abs(v)<=1));}for(const width of [375,1440]){await page.setViewportSize({width,height:1000});await wait(200);const dims=await page.locator('canvas').evaluateAll(cs=>cs.map(c=>({w:c.width,h:c.height,cw:c.clientWidth,ch:c.clientHeight,d:devicePixelRatio,pixels:c.getContext('2d').getImageData(0,0,c.width,c.height).data.some(v=>v)})));assert(dims.every(c=>c.w===Math.round(c.cw*c.d)&&c.h===Math.round(c.ch*c.d)&&c.pixels));}});
 await row('G25',async()=>{await next(()=>window.audit.snapshot.timeline.length>=3,15000);const s=await snap();assert(s.timeline.length>=3);assert(await page.locator('.cap-title').isVisible());for(const c of s.timeline){assert(c.cites.length>0);assert(c.cites.every(id=>c.evidence.some(e=>e.id===id)));assert(c.explain.includes('[E'));}await has('rule floor');});
 await row('G26',async()=>{await has('Rules + template (no model call)');await has('captures · rules + templates explain, citing evidence');assert((await snap()).timeline.every(c=>c.by==='rules'));});
 await row('G27',async()=>{assert.equal(await page.locator('.loop-cell').count(),3);await has('Rules →');await has('cites');assert((await page.locator('.loop-cell').nth(0).innerText()).includes('CH2'));});
 await row('G28',async()=>{const b=page.locator('.cite').first();await b.focus();const id=(await b.innerText()).trim();assert.equal(await page.locator(`.ev.is-on .ev-id`).innerText(),id);await b.click();assert(await page.locator('.ev.is-on').isVisible());});
 await row('G16',async()=>{await page.locator('.acq-cap').first().click();assert.equal(await page.locator('.cap-title').innerText(),'Got up');await page.getByRole('button',{name:'Back to the latest capture',exact:true}).click();assert.notEqual(await page.locator('.cap-title').innerText(),'Got up');});
 await row('G29',async()=>{await page.locator('.acq-cap').first().click();const count=(await snap()).timeline.length;await next(new Function(`return window.audit.snapshot.timeline.length>${count}`),20000);assert.equal(await page.locator('.cap-title').innerText(),'Got up');assert.equal(await page.locator('.cap-row[aria-current=true]').count(),1);const ids=await page.locator('.cap-row .cap-row-ev').allTextContents();assert.equal(ids.at(-1),'Got up');await page.getByRole('button',{name:'Back to the latest capture',exact:true}).click();});
 await row('G30',async()=>{await next(()=>document.querySelectorAll('.mod.is-linked').length===4,12000);assert.equal(await page.locator('.room.is-linked').count(),1);assert.equal(await page.locator('.trace.is-linked').count(),1);await wait(4000);assert.equal(await page.locator('.mod.is-linked').count(),0);});
 await row('G32',async()=>{await next(()=>window.audit.snapshot.lamp.state.eye==='red',25000);const seen=await page.evaluate(()=>window.audit.seen);assert(seen.some(s=>s.lamp.state.eye==='path'&&s.lamp.state.pan===-47));assert(seen.some(s=>s.lamp.state.eye==='amber'&&s.lamp.state.speaking));assert(seen.some(s=>s.lamp.state.listening));assert.equal((await snap()).lamp.state.pan,7);});
 await row('G38',async()=>{const s=await snap();assert.deepEqual(s.timeline.map(c=>[c.event,c.room,c.severity]),[['got_up','bedroom','watch'],['moved','bathroom','watch'],['fall_suspected','bathroom','watch'],['long_stay','bathroom','check_in'],['no_answer','bathroom','alert']]);assert.equal(s.timeline.at(-1).outcome,'family alerted (dry run: replay never places real calls)');assert(!network.some(r=>/twilio|telegram/i.test(r.url)));assert.equal(fs.readFileSync(path.join(out,'hub-network.jsonl'),'utf8'),'');return JSON.stringify({events:s.timeline.map(c=>[c.event,c.room,c.severity]),outcome:s.timeline.at(-1).outcome,hubOutboundConnections:0});});
 await row('G39',async()=>{const s=await snap();assert(await page.locator('.cmd-log li').count()<=6);assert(s.lamp.recent.every(c=>!['level','ping'].includes(c.op)));const cmd=await page.locator('.cmd-log li').allTextContents();assert(cmd.length>0);});
 await row('G42',async()=>{await next(()=>window.audit.snapshot.replay.done,15000);const t=(await snap()).clock;await wait(700);assert.equal((await snap()).clock,t);await page.getByRole('button',{name:'Run the night again',exact:true}).click();await next(()=>window.audit.snapshot.replay.pos<1);assert.equal((await snap()).timeline.length,0);});
 await row('G34',async()=>{await checkin();await next(()=>window.audit.snapshot.lamp.state.listening,10000);await page.getByRole('button',{name:"Tap HOTARU's button: I'm OK",exact:true}).click();await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'));const s=await snap();assert.equal(s.timeline.filter(c=>c.event==='answered').length,1);assert(!s.timeline.some(c=>c.event==='no_answer'));assert.equal(s.lamp.state.eye,'path');assert.equal(s.lamp.state.action,'nod');assert.equal(s.timeline.find(c=>c.event==='long_stay').outcome,'answered by button');await has('Stood down: answered by button');});
 await row('G35',async()=>{await checkin();assert((await snap()).lamp.state.speaking);assert(!(await snap()).lamp.state.listening);await page.getByRole('button',{name:"Tap HOTARU's button: I'm OK",exact:true}).click();await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'),10000);await wait(1000);assert(!(await snap()).timeline.some(c=>c.event==='no_answer'));});
 await row('G36',async()=>{await checkin();await next(()=>window.audit.snapshot.lamp.state.listening,10000);await next(()=>window.audit.snapshot.lamp.state.checkin&&!window.audit.snapshot.lamp.state.listening&&!window.audit.snapshot.lamp.state.speaking,10000);await page.getByRole('button',{name:"Tap HOTARU's button: I'm OK",exact:true}).click();await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'));assert(!(await snap()).lamp.state.checkin);assert(await page.getByRole('button',{name:"HOTARU's button (arms on a check-in)",exact:true}).isDisabled());});
 await row('G37',async()=>{await fresh();assert.equal((await post('lamp/tap')).status,200);await wait(600);assert.equal((await snap()).timeline.length,0);await checkin();await post('lamp/tap');await post('lamp/tap');await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'));assert.equal((await snap()).timeline.filter(c=>c.event==='answered').length,1);});
 await row('G40',async()=>{await checkin();await page.getByRole('button',{name:'Stop the replay',exact:true}).click();await next(()=>window.audit.snapshot.replay.paused);const s=await snap();await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='no_answer'),20000);const a=await snap();assert.equal(a.replay.pos,s.replay.pos);assert.equal(a.timeline.at(-1).t,a.now);await page.getByRole('button',{name:'Run the replay',exact:true}).click();await wait(700);assert.equal((await snap()).timeline.filter(c=>c.event==='no_answer').length,1);});
 await row('G41',async()=>{for(const action of ['replay/restart','replay/jump']){await checkin();await post(action);await next(()=>window.audit.snapshot.timeline.length===0);await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);await wait(16000);assert.equal((await snap()).timeline.length,0);assert(!(await snap()).lamp.state.checkin);}});
 await row('G48',async()=>{await post('replay/resume');const p=await observed(await ctx.newPage());const n=network.length;await p.goto(base+'/?once=1');await p.waitForSelector('.bench');const clock=await p.getByLabel('Scene time').innerText();await wait(1200);assert.equal(await p.getByLabel('Scene time').innerText(),clock);assert.equal(await p.evaluate(()=>window.audit.created),0);assert.equal(network.slice(n).filter(r=>r.event==='request'&&r.url.endsWith('/api/state')).length,1);assert.notEqual((await snap()).clock,clock);intentionalClosures.add(p);await p.close();});
 await row('G82',async()=>{const p=await observed(await ctx.newPage());await p.goto(base);await next(()=>!!window.audit.snapshot,15000,p);await page.getByRole('button',{name:'Stop the replay',exact:true}).click();await next(()=>window.audit.snapshot.replay.paused,15000,p);assert.equal((await snap(p)).replay.pos,(await snap()).replay.pos);await p.getByRole('button',{name:'2×',exact:true}).click();await next(()=>window.audit.snapshot.replay.speed===2);await p.getByRole('button',{name:'Restart the night from 02:50',exact:true}).click();await next(()=>window.audit.snapshot.replay.pos<1);intentionalClosures.add(p);await p.close();await wait(700);assert((await snap()).replay.pos>0);});
 // Actual outage, then restart the same built hub; only these induced transport failures are expected.
 await row('G5',async()=>{await stop();await page.getByText('Lost the hub.',{exact:true}).waitFor();await has('Hub link lost · retrying');await start();await next(()=>document.querySelector('.plate-clock-note').textContent.includes('Replay'));},{expectedFault:true});
 await row('G50',async()=>{await stop();await page.getByRole('button',{name:'Restart the night from 02:50',exact:true}).click();await page.getByRole('alert').waitFor();await has("The hub didn't answer. Is python -m hub.server still running?");await start();await page.getByRole('button',{name:'Restart the night from 02:50',exact:true}).click();await next(()=>window.audit.snapshot.replay.pos<2);assert.equal(await page.getByRole('alert').count(),0);},{expectedFault:true});
 await row('G52',async()=>{await stop();await wait(1900);assert.equal(await page.evaluate(()=>window.audit.active),0);await start();await next(()=>window.audit.active===1&&document.querySelector('.plate-clock-note').textContent.includes('Replay'));assert.equal(await page.evaluate(()=>window.audit.active),1);const p=await observed(await ctx.newPage());await p.goto(base);await next(()=>window.audit.active===1,15000,p);await p.goto('about:blank');assert.equal(network.filter(r=>r.event==='request'&&r.url.includes('tokenfactory')).length,0);intentionalClosures.add(p);await p.close();},{expectedFault:true});
 await row('G49',async()=>{let release;const gate=new Promise(r=>release=r);const p=await observed(await ctx.newPage());await p.route('**/api/state',async r=>{await gate;await r.continue().catch(()=>{});});await p.goto(base+'/?once=1');await stop();release();await p.getByText('Lost the hub.',{exact:true}).waitFor();assert((await p.locator('body').textContent()).includes('/api/stream'));assert((await p.locator('body').textContent()).includes('Hub link lost · retrying'));assert.equal(await p.locator('.bench').count(),0);intentionalClosures.add(p);await p.close();await start();await next(()=>document.querySelector('.plate-clock-note').textContent.includes('Replay'));},{expectedFault:true});
 await checkin();await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);await page.setViewportSize({width:375,height:812});
 for(const id of ['G53','G54','G55','G56','G57','G58','G59'])await row(id,async()=>{
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'page horizontal overflow');
   const selector={G53:'.plate',G54:'.acq',G55:'.m-plan',G56:'.m-traces',G57:'.m-trigger',G58:'.m-hotaru',G59:'.m-mask'}[id];await page.locator(selector).scrollIntoViewIfNeeded();
   const rect=await page.locator(selector).boundingBox();assert(rect.x>=0&&rect.x+rect.width<=375);
   if(id==='G53'){await has('Setup required: NEBIUS_API_KEY');assert.equal(await page.locator('.plate-lamp-value').evaluateAll(es=>es.some(e=>e.scrollWidth>e.clientWidth)),false);}
   if(id==='G54')assert.equal(await page.locator('.acq-keys button').count(),6);
   if(id==='G55')assert.equal(await page.locator('.room-name').count(),5);
   if(id==='G56'){assert.equal(await page.locator('canvas').count(),4);assert(await page.locator('.trace-read div').filter({hasText:'Motion'}).first().isVisible());}
   if(id==='G57'){const b=page.getByRole('button',{name:/Show all evidence/});if(await b.count()){await b.click();assert.equal(await page.locator('.ev').count(),(await snap()).timeline.at(-1).evidence.length);}}
   if(id==='G58'){assert(await page.locator('.key-tap').isEnabled());assert(await page.locator('.key-tap').isVisible());assert.equal(await page.locator('.key-tap').evaluate(e=>e.scrollWidth>e.clientWidth),false);}
   if(id==='G59'){const order=await page.locator('.mod').evaluateAll(es=>es.sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top).map(e=>e.getAttribute('aria-label')));assert.deepEqual(order,['Trigger','Plan','Breathing','HOTARU','Routine','Log']);}
 });
 await row('G60',async()=>{
   const n=network.length;await page.locator('.key-tap').focus();await page.keyboard.press('Enter');
   await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'));
   assert.equal(network.slice(n).filter(r=>r.event==='request'&&r.url.endsWith('/lamp/tap')).length,1);
   await page.keyboard.press('Tab');
   for(const sel of ['.acq-keys button','.cite','.cap-row']){const b=page.locator(sel).first();if(await b.count()){await b.focus();assert.equal(await b.evaluate(e=>document.activeElement===e),true);assert.notEqual(await b.evaluate(e=>getComputedStyle(e).outlineStyle),'none');}}
   const p=await observed(await ctx.newPage());await p.setViewportSize({width:375,height:812});await p.goto(base);await next(()=>!!window.audit.snapshot,15000,p);
   const history=p.locator('.cap-row').filter({hasText:'Long stay'}).first();await history.focus();await p.keyboard.press('Enter');
   await p.waitForFunction(()=>document.querySelector('.cap-title').textContent==='Long stay');
   const expand=p.getByRole('button',{name:/Show all evidence/});assert(await expand.isVisible());await expand.focus();await p.keyboard.press('Enter');
   const selected=(await snap(p)).timeline.find(c=>c.event==='long_stay');assert.equal(await p.locator('.ev').count(),selected.evidence.length);
   const cite=p.locator('.cite').first();await cite.focus();await p.keyboard.press('Enter');assert.equal(await p.locator('.ev.is-on').count(),1);
   intentionalClosures.add(p);await p.close();
   let at=network.length;await page.getByRole('button',{name:'1×',exact:true}).focus();await page.keyboard.press('Enter');await next(()=>window.audit.snapshot.replay.speed===1);
   assert.equal(network.slice(at).filter(r=>r.event==='request'&&r.url.endsWith('/speed?x=1')).length,1);
   for(const [name,route,condition] of [
     ['Run the replay','resume',()=>!window.audit.snapshot.replay.paused],
     ['Stop the replay','pause',()=>window.audit.snapshot.replay.paused],
     ['Restart the night from 02:50','restart',()=>window.audit.snapshot.replay.pos<1],
     ['Jump to just before he gets up','jump',()=>window.audit.snapshot.replay.pos>=36],
   ]){at=network.length;await page.getByRole('button',{name,exact:true}).focus();await page.keyboard.press('Enter');await next(condition);assert.equal(network.slice(at).filter(r=>r.event==='request'&&r.url.endsWith('/replay/'+route)).length,1);}
   assert(await page.getByLabel('Scene time').isVisible());assert(await page.getByLabel('System status').isVisible());
 });
 await row('G61',async()=>{
   await page.emulateMedia({reducedMotion:'reduce'});
   intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);
   await next(()=>!!window.audit.snapshot);await fresh();await jump();await speed();
   await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='no_answer'),40000);
   assert.equal(await page.locator('.room-breath').evaluateAll(es=>es.some(e=>getComputedStyle(e).animationName!=='none')),false);
   const failures=await page.evaluate(()=>{
     const color=c=>{const n=c.match(/[\d.]+/g).map(Number),scale=c.startsWith('color(srgb')?1:255;return [n[0]/scale,n[1]/scale,n[2]/scale,n[3]??1];};
     const over=(top,bottom)=>{const a=top[3]+bottom[3]*(1-top[3]);return a?[0,1,2].map(i=>(top[i]*top[3]+bottom[i]*bottom[3]*(1-top[3]))/a).concat(a):[0,0,0,0];};
     const lum=c=>{const a=c.slice(0,3).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return .2126*a[0]+.7152*a[1]+.0722*a[2];};
     const cache=new WeakMap();
     const backgrounds=e=>{if(!e)return [[1,1,1,1]];if(cache.has(e))return cache.get(e);const s=getComputedStyle(e),base=color(s.backgroundColor),stops=s.backgroundImage.match(/rgba?\([^)]+\)/g);const own=stops?stops.map(c=>over(color(c),base)):[base];const out=own.flatMap(c=>backgrounds(e.parentElement).map(b=>over(c,b)));cache.set(e,out);return out;};
     return [...document.querySelectorAll('body *')]
       .filter(e=>e instanceof HTMLElement&&[...e.childNodes].some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim())&&e.getBoundingClientRect().width>2&&e.getBoundingClientRect().height>2&&!e.closest('button:disabled')&&getComputedStyle(e).visibility!=='hidden')
       .flatMap(e=>{const s=getComputedStyle(e),fg=color(s.color),bgs=backgrounds(e);const ratios=bgs.map(bg=>{const a=lum(over(fg,bg)),b=lum(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);});const ratio=Math.min(...ratios),size=parseFloat(s.fontSize),large=size>=24||(size>=18.66&&parseInt(s.fontWeight)>=700);return ratio<(large?3:4.5)?[{text:e.textContent,ratio,color:s.color,backgrounds:bgs}]:[];});
   });
   assert.deepEqual(failures,[]);
 });

 await row('G64',async()=>{const r=await page.request.get(base);assert.equal(r.status(),200);assert.equal(r.headers()['cache-control'],'no-store');assert(r.headers()['content-type'].includes('text/html'));const assets=await page.locator('script[src],link[href]').evaluateAll(es=>es.map(e=>e.src||e.href));for(const url of assets.filter(x=>x.startsWith(base))){const q=await page.request.get(url);assert.equal(q.status(),200);network.push({event:'direct-response',status:q.status(),url,type:q.headers()['content-type']});}assert(!network.some(r=>r.url.includes(':5178')));});
 async function raw(request){return new Promise((resolve,reject)=>{const c=net.connect(port,'127.0.0.1');const chunks=[];c.on('connect',()=>{c.write(request);c.end();});c.on('data',d=>chunks.push(d));c.on('end',()=>resolve(Buffer.concat(chunks).toString()));c.on('error',reject);c.setTimeout(3000,()=>{c.destroy();reject(new Error('raw timeout'));});});}
 await row('G65',async()=>{for(const uri of ['/../hub/server.py','/../../../../etc/passwd','/assets/','/not-present.js']){const r=await raw(`GET ${uri} HTTP/1.1\r\nHost: localhost\r\n\r\n`);assert(r.startsWith('HTTP/1.1 404'));assert(r.endsWith('not found'));network.push({event:'expected-raw-response',url:base+uri,status:404});}},{expectedFault:true});
 await row('G66',async()=>{const r=await page.evaluate(async()=>{const r=await fetch('api/state');return {status:r.status,type:r.headers.get('content-type'),s:await r.json()};});assert.equal(r.status,200);assert.equal(r.type,'application/json');for(const k of ['mode','now','clock','home','rooms','followed','routine','timeline','lamp','model','log','replay'])assert(k in r.s);assert.equal(Object.keys(r.s.rooms).length,5);assert(!JSON.stringify(r.s).match(/NaN|Infinity/));});
 await row('G67',async()=>{await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);const a=await snap();const r=await post('state');assert.equal(r.status,200);const b=JSON.parse(r.body);assert.equal(b.now,a.now);assert.deepEqual(b.timeline,a.timeline);});
 await row('G68',async()=>{
   intentionalClosures.add(page);
   const r=await page.evaluate(async()=>{
     const r=await fetch('api/stream'),reader=r.body.getReader(),decoder=new TextDecoder();let pending='';
     const event=async()=>{while(!pending.includes('\n\n')){const chunk=await reader.read();if(chunk.done)throw new Error('SSE ended before an event');pending+=decoder.decode(chunk.value,{stream:true});}const end=pending.indexOf('\n\n')+2,result=pending.slice(0,end);pending=pending.slice(end);return result;};
     const first=await event(),at=performance.now(),second=await event(),delta=performance.now()-at;await reader.cancel();
     return {status:r.status,type:r.headers.get('content-type'),cache:r.headers.get('cache-control'),connection:r.headers.get('connection'),first,second,delta};
   });
   await wait(100);intentionalClosures.delete(page);assert.equal(r.status,200);assert.equal(r.type,'text/event-stream');assert.equal(r.connection,'keep-alive');assert.equal(r.cache,'no-store');
   assert(r.first.startsWith('data: ')&&r.first.endsWith('\n\n'));JSON.parse(r.first.slice(6));JSON.parse(r.second.slice(6));
   assert(r.delta>300&&r.delta<1500);return JSON.stringify({status:r.status,type:r.type,cache:r.cache,connection:r.connection,eventSpacingMs:r.delta});
 });
 await row('G69',async()=>{assert.equal((await post('replay/restart')).status,200);await next(()=>window.audit.snapshot.replay.pos<1);const s=await snap();assert.equal(s.replay.speed,1);assert.equal(s.timeline.length,0);assert.equal(s.log.length,0);});
 await row('G70',async()=>{assert.equal((await post('replay/jump')).status,200);await next(()=>window.audit.snapshot.replay.pos>=36);assert.equal((await snap()).timeline.length,0);});
 await row('G71',async()=>{await post('replay/pause');await next(()=>window.audit.snapshot.replay.paused);const p=(await snap()).replay.pos;assert.equal((await post('replay/pause')).status,200);await wait(650);assert.equal((await snap()).replay.pos,p);});
 await row('G72',async()=>{const p=(await snap()).replay.pos;assert.equal((await post('replay/resume')).status,200);assert.equal((await post('replay/resume')).status,200);await wait(1100);const s=await snap();assert(!s.replay.paused);assert(s.replay.pos>p&&s.replay.pos<p+2);});
 await row('G73',async()=>{await post('replay/pause');for(const [query,value] of [['?x=2',2],['',1],['?x=',1],['?x=2&x=4',4]]){const r=await post('replay/speed'+query);assert.equal(r.status,200);await next(new Function(`return window.audit.snapshot.replay.speed===${value}`));}});
 await row('G74',async()=>{for(const [value,expected] of [['0',.25],['-1',.25],['.1',.25],['10',4],['.25',.25],['4',4]]){assert.equal((await post('replay/speed?x='+value)).status,200);await next(new Function(`return window.audit.snapshot.replay.speed===${expected}`));}});
 await row('G75',async()=>{const before=(await snap()).replay.speed;for(const value of ['banana','NaN','Infinity']){const r=await post('replay/speed?x='+value);assert.equal(r.status,400);assert(JSON.parse(r.body).error.includes('finite'));await wait(550);assert.equal((await snap()).replay.speed,before);}},{expectedFault:true});
 await row('G76',async()=>{await checkin();const r=await post('lamp/tap');assert.equal(r.status,200);assert.deepEqual(JSON.parse(r.body),{ok:true});await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'));});
 await row('G78',async()=>{const r=await post('not-a-real-action');assert.equal(r.status,404);assert.deepEqual(JSON.parse(r.body),{error:'unknown action'});assert.equal((await post('replay/pause')).status,200);},{expectedFault:true});
 await row('G79',async()=>{for(const uri of ['replay/restart','replay/jump','replay/pause','replay/resume','replay/speed','lamp/tap','not-real']){const r=await page.evaluate(async uri=>{const r=await fetch('api/'+uri);return {status:r.status,body:await r.text()};},uri);assert.equal(r.status,404);assert.equal(r.body,'not found');}},{expectedFault:true});
 await row('G80',async()=>{for(const method of ['PUT','PATCH','DELETE','OPTIONS','HEAD'])for(const uri of ['api/state','']){const r=await page.evaluate(async({method,uri})=>{const r=await fetch(uri||'./',{method});return {status:r.status,body:await r.text()};},{method,uri});assert.equal(r.status,405);assert.equal(r.body,'');}for(const uri of ['./',await page.locator('script[src]').getAttribute('src')]){const r=await page.evaluate(async uri=>{const r=await fetch(uri,{method:'POST'});return {status:r.status,body:await r.text()};},uri);assert.deepEqual(r,{status:405,body:''});}},{expectedFault:true});
 await row('G81',async()=>{for(const q of ['bad\r\n\r\n','GET / HTTP/1.1\r\n','POST /api/state HTTP/1.1\r\nContent-Length: banana\r\n\r\n','POST /api/state HTTP/1.1\r\nContent-Length: 10\r\n\r\nx'])assert.equal(await raw(q),'');const r=await page.evaluate(async()=>{const r=await fetch('api/state');return r.status;});assert.equal(r,200);});
 await row('G45',async()=>{await stop();await start(['--live','--lamp-port','38770']);intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.mode==='live');await has('No routine yet: GHOST needs a few days of presence before it knows what normal is.');assert.equal((await snap()).routine,null);assert(Object.values((await snap()).rooms).every(r=>r.routine_p===undefined));},{expectedFault:true});
 await row('G77',async()=>{assert.equal((await snap()).lamp.connected,false);await has('Waiting for HOTARU');const r=await post('lamp/tap');assert.equal(r.status,409);assert.deepEqual(JSON.parse(r.body),{error:'no virtual HOTARU to tap'});},{expectedFault:true});
 await row('G83',async()=>{for(const act of ['pause','resume','speed','jump']){const r=await post('replay/'+act);assert.equal(r.status,404);assert.deepEqual(JSON.parse(r.body),{error:'unknown action'});}const r=await post('replay/restart');assert.equal(r.status,200);await wait(600);assert.equal((await snap()).mode,'live');await stop();await start();intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.mode==='replay');},{expectedFault:true});

 await row('G85',async()=>{const file=path.join(observerDir,'custom.ghostcsi');const make=spawnSync(path.join(root,'.venv/bin/python'),['-c',`from hub.replay import Recording, Writer; from hub import scenario; r=Recording.load(scenario.ensure_night()); w=Writer('${file}', dict(r.header, scale=10, markers=r.header['markers'][:2])); [w.frame(t,f.source,f.lamp_ms,f.rssi,f.amp) for t,f in r.frames]; w.close()`],{cwd:root,env,encoding:'utf8'});assert.equal(make.status,0);await stop();await start(['--recording',file,'--speed','2']);intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.replay.speed===2);assert.equal((await snap()).replay.scale,10);assert.equal((await snap()).replay.markers.length,2);await has('synthetic night');await post('replay/restart');await next(()=>window.audit.snapshot.replay.pos<2);assert.equal((await snap()).replay.speed,2);const empty=path.join(observerDir,'plain.ghostcsi');const r=spawnSync(path.join(root,'.venv/bin/python'),['-c',`from hub.replay import Writer; import time; Writer('${empty}', {'scene_start':time.time(),'scale':1,'markers':[]}).close()`],{cwd:root,env,encoding:'utf8'});assert.equal(r.status,0);await stop();await start(['--recording',empty,'--speed','2']);intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.replay.done);assert.equal((await snap()).replay.synthetic,false);assert(!(await page.locator('body').textContent()).includes('synthetic night'));assert.equal((await snap()).replay.speed,2);},{expectedFault:true});
 await row('G87',async()=>{const file=path.join(observerDir,'empty.ghostcsi');const r=spawnSync(path.join(root,'.venv/bin/python'),['-c',`from hub.replay import Writer; import time; Writer('${file}', {'scene_start':time.time(),'scale':1,'markers':[]}).close()`],{cwd:root,env,encoding:'utf8'});assert.equal(r.status,0);await stop();await start(['--recording',file]);intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.replay.done);const s=await snap();assert.equal(s.replay.duration,0);assert.equal(s.timeline.length,0);assert.equal(s.routine,null);assert(Object.values(s.rooms).every(r=>r.state==='waiting'||r.state==='no sensor'));assert(!(await page.locator('body').textContent()).includes('synthetic night'));assert(!(await page.locator('body').textContent()).includes('The bundled night'));assert.equal(await page.locator('[style*="NaN"]').count(),0);await stop();await start();intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>window.audit.snapshot?.replay.synthetic);},{expectedFault:true});
 await row('G88',async()=>{await stop();await start(['--reply',"I'm OK"]);intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>!!window.audit.snapshot);await jump();await speed();await next(()=>window.audit.snapshot.timeline.some(c=>c.event==='answered'),40000);const s=await snap();assert.equal(s.timeline.find(c=>c.event==='long_stay').outcome,'answered by voice');assert(!s.timeline.some(c=>c.event==='no_answer'));assert.equal(s.lamp.kind,'virtual');assert.equal(s.lamp.state.action,'nod');assert.equal(s.lamp.state.eye,'path');await has("Heard: I'm OK");await stop();await start();intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>!!window.audit.snapshot);},{expectedFault:true});
 // Real HTTP errors appear in UI by swapping the live local session, not mocking a response.
 await page.setViewportSize({width:1440,height:1000});
 await row('G51',async()=>{let release;const gate=new Promise(r=>release=r);await page.route('**/api/stream',async r=>{await gate;await r.continue().catch(()=>{});});await stop();await start(['--live','--lamp-port','38770']);await page.getByRole('button',{name:'Stop the replay',exact:true}).click();await has('unknown action');await page.getByRole('button',{name:'Restart the night from 02:50',exact:true}).click();await page.getByRole('alert').waitFor({state:'hidden'});release();await page.unrouteAll({behavior:'wait'});await stop();await start();intentionalClosures.add(page);await page.reload();intentionalClosures.delete(page);await next(()=>!!window.audit.snapshot);},{expectedFault:true});
 await row('G62',async()=>{const normal=results.filter(r=>!JSON.parse(fs.readFileSync(path.join(root,r.log))).expectedFault);const bad=normal.filter(r=>{const l=JSON.parse(fs.readFileSync(path.join(root,r.log)));return l.pageErrors.length||l.console.some(c=>c.type==='error');});assert.deepEqual(bad.map(r=>r.id),[]);});
 await row('G63',async()=>{const bad=results.filter(r=>!JSON.parse(fs.readFileSync(path.join(root,r.log))).expectedFault).filter(r=>JSON.parse(fs.readFileSync(path.join(root,r.log))).network.some(x=>x.event==='failed'||x.status>=400));assert.deepEqual(bad.map(r=>r.id),[]);assert.equal(network.filter(x=>/tokenfactory|twilio|telegram/i.test(x.url)).length,0);});
 fs.writeFileSync(path.join(out,'network-all.json'),JSON.stringify(network,null,2));fs.writeFileSync(path.join(out,'console-all.json'),JSON.stringify({console:consoleLog,pageErrors},null,2));
}catch(e){console.error(e.stack);process.exitCode=1;}
finally{await cleanup();}

