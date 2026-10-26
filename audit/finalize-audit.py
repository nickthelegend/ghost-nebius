"""Merge only a complete, verified final run into the Phase 1 table."""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
untested={116,117,119,120,121,122,123,124,125,126,127,128}
results={}
for group in ('browser','local'):
    for row in json.loads((root/f'audit/{group}/results.json').read_text()):
        assert row['id'] not in results, row['id']
        results[row['id']]=row
sequence=[json.loads(line) for line in (root/'audit/sequence.jsonl').read_text().splitlines()]
assert [r['id'] for r in sequence]==[f'G{i}' for i in range(1,135)], 'audit must run top to bottom'
assert all(r['status']==('UNTESTED' if int(r['id'][1:]) in untested else 'PASS') for r in sequence)
assert all(a['finishedAt']<=b['startedAt'] for a,b in zip(sequence,sequence[1:])), 'rows overlap'
assert not json.loads((root/'audit/browser/console-all.json').read_text())['pageErrors']
assert not (root/'audit/browser/hub-network.jsonl').read_text(), 'hub made outbound connections'
assert not json.loads((root/'audit/browser/cleanup.json').read_text())['remaining']
pytest_summary=re.search(r'^(\d+) passed in ([\d.]+)s(?: \(.*\))?$', (root/'audit/pytest-final.txt').read_text(), re.M)
assert pytest_summary, 'pytest must end in a passing-only summary'
collected=json.loads((root/'audit/local/G131.json').read_text())['note']
assert f'{pytest_summary[1]} tests collected' in collected, 'pytest execution and collected counts differ'
expected={f'G{i}' for i in range(1,135) if i not in untested}
assert set(results)==expected, f'missing: {sorted(expected-set(results))}'
failures=[r for r in results.values() if r['status']!='PASS']
assert not failures, [(r['id'],r['note']) for r in failures]
for r in results.values():
    log=json.loads((root/r['log']).read_text())
    assert log['status']=='PASS', r['id']
    if r['log'].startswith('audit/local/'):
        assert all(event['address'].startswith(("('127.0.0.1',", "('::1',")) for event in log['network']), r['id']+' made an external connection'
    assert not log.get('pageErrors'), r['id']
    assert not log.get('unexpectedConsole') and not log.get('unexpectedNetwork'), r['id']
    if 'screenshot' in r:
        assert (root/r['screenshot']).is_file()
        assert (root/r['screenshot']).stat().st_size<=200000
assert results['G8']['status']=='PASS'

fixes={
 'G5':'Expose the lost link and label retained values as the last snapshot (ad63e47).',
 'G7':'Keep warm-up rooms waiting until a measured reading exists (320040f).',
 'G8':'Show Setup required: NEBIUS_API_KEY in the Reason lamp; keep rules/templates and model.online=false (df8f368).',
 'G13':'Clear stale capture highlights together with pinned selection on restart (f39ce54).',
 'G18':'Do not report invented empty-room readings during sensor warm-up (320040f).',
 'G30':'Clear stale chain highlights when a session resets (f39ce54).',
 'G35':'Latch armed taps during speech before the listening waiter exists (771a715).',
 'G36':'Keep the check-in armed through the silent grace interval (771a715).',
 'G37':'Retain one armed button answer and disarm the completed check-in (771a715).',
 'G40':'Disarm check-ins in finally while preserving wall-clock speech/listening (771a715).',
 'G41':'Await cancelled replay/decision workers before replacing the session and disarm the old check-in (771a715).',
 'G48':'Abort the frozen request on unmount and reject non-success responses (ad63e47).',
 'G49':'Reject failed frozen state responses and keep the real lost-hub state (ad63e47).',
 'G56':'Keep the motion readout visible at phone widths (459b4bd).',
 'G61':'Use AA-compliant alert, secondary-screen and selected-key hover text colors (f5eab36, 35da99a, 7097c1f).',
 'G69':'Finish cancellation before starting the new session (771a715).',
 'G70':'Finish cancellation before pre-rolling the new session (771a715).',
 'G73':'Use the final query value and default an empty value to 1 (8c5d12c).',
 'G74':'Clamp only validated finite speed values to 0.25–4 (8c5d12c).',
 'G75':'Return 400 for invalid/nonfinite speeds without changing the prior speed (8c5d12c).',
 'G80':'Restrict the state compatibility route to GET/POST; reject unsupported methods with 405 (8c5d12c).',
 'G81':'Close malformed/truncated requests without an unhandled HTTP task error (8c5d12c).',
 'G83':'Allow a local live Session to run without a connected lamp (02817ea).',
 'G85':'Do not inject the synthetic routine into an unlabelled recording (cae7bcb).',
 'G86':'Reject truncated room names, frame headers and amplitude payloads (d420a2d).',
 'G87':'Keep a zero-duration playhead finite and the unlearned routine empty (a83fdc7, cae7bcb).',
 'G94':'Validate routine CLI arguments and report input errors before changing files (ba5a629).',
 'G100':'Use one sampled timestamp for saves and daily refits; verify the real persisted journal across an eligible day and repeated ticks (917b3f4).',
 'G97':'Describe routine fit/show as local JSON work; Serverless remains planned/optional (341b134).',
 'G113':'Discard incomplete CSI amplitude payloads (02e4ed3).',
 'G130':'Rebuilt web/dist in each frontend fix commit; served through the Python hub.',
 'G131':f'The independent full suite and collection both report {pytest_summary[1]} tests; see audit/pytest-final.txt.',
 'G134':'Make missing-key setup explicit and remove any synthetic-routine injection into unlabelled recordings (df8f368, cae7bcb, 341b134).',
}
original=subprocess.check_output(['git','show','02e4ed3^:AUDIT.md'],cwd=root,text=True)
original_expected={line.split('|')[1].strip():line.split('|')[3].strip() for line in original.splitlines() if re.match(r'^\| G\d+ \|',line)}
current_expected={line.split('|')[1].strip():line.split('|')[3].strip() for line in (root/'AUDIT.md').read_text().splitlines() if re.match(r'^\| G\d+ \|',line)}
assert current_expected==original_expected, 'expected results changed during the audit'
lines=[];deps={}
for line in original.splitlines():
    match=re.match(r'^\| (G\d+) \|',line)
    if match:
        id=match[1];cols=[c.strip() for c in line.split('|')[1:-1]]
        assert len(cols)==6
        assert cols[2]==original_expected[id], id+' expected result changed'
        if int(id[1:]) in untested:
            assert cols[3]=='UNTESTED'
            dependency=cols[5]
            deps[id]=dependency
            cols[4]='[missing dependency](audit/dependencies.json)'
        else:
            r=results[id];cols[3]=r['status']
            screenshot=r.get('screenshot','audit/browser/G1.webp')
            label='screenshot' if 'screenshot' in r else 'dashboard context'
            cols[4]=f'[{label}]({screenshot}) · [console/network or CLI assertions]({r["log"]})'
            if id=='G7': cols[4]+=' · [disconnected lamp](audit/browser/G77.json)'
            if id=='G8': cols[4]+=' · [capture attribution](audit/browser/G26.json) · [hub outbound connections](audit/browser/hub-network.jsonl)'
            if id=='G38': cols[4]+=' · [hub outbound connections](audit/browser/hub-network.jsonl)'
            cols[5]=fixes.get(id,'—')
        line='| '+' | '.join(cols)+' |'
    elif re.match(r'^134 rows,',line):
        line='134 rows, 122 PASS, 0 FAIL, 12 UNTESTED.'
    lines.append(line)
lines.append('Final independent rerun: 2026-10-26 · [ordered record](audit/sequence.jsonl) · [run metadata](audit/run.json) · [cleanup](audit/resource-cleanup.json).')
(root/'AUDIT.md').write_text('\n'.join(lines)+'\n')
(root/'audit/dependencies.json').write_text(json.dumps(deps,indent=2)+'\n')
assert deps['G116']=='needs NEBIUS_API_KEY' and deps['G117']=='needs NEBIUS_API_KEY'
counts=Counter(line.split('|')[4].strip() for line in lines if re.match(r'^\| G\d+ \|',line))
assert counts=={'PASS':122,'UNTESTED':12}, counts
size=sum(p.stat().st_size for p in (root/'audit').rglob('*') if p.is_file())
assert size<15*1024*1024, size
print(dict(counts), 'audit_bytes',size)
