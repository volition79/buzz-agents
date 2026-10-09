'use strict';
const $ = id => document.getElementById(id);
let configured = false, authSession = null, pollBusy = false, tick = 0;
const errors = {
  invalid_or_expired_setup_code: '최초 설정 코드가 틀리거나 만료되었습니다. Docker Manager에서 portal을 재시작하면 새 코드를 확인할 수 있습니다.',
  invalid_settings_password: '설정 화면 비밀번호가 맞지 않습니다.',
  settings_password_minimum_12_characters: '설정 화면 비밀번호는 12자 이상이어야 합니다.',
  settings_login_required: '설정 화면에 다시 로그인해 주세요.',
  try_again_in_one_minute: '요청이 많습니다. 1분 후 다시 시도해 주세요.',
  configure_relay_first: '먼저 내 Relay를 연결해 주세요.',
  existing_relay_configuration_preserved: '이미 연결된 Relay 설정은 자동으로 변경하지 않습니다.',
  connection_program_not_packaged: 'Windows 연결 프로그램이 아직 이미지에 포함되지 않았습니다.',
  stop_bot_before_authentication: '실행 중인 봇을 Buzz에서 중지한 뒤 로그인해 주세요.',
  existing_installation_requires_migration: '이전 설치 데이터가 있습니다. 자동으로 덮어쓰지 않습니다.',
  login_session_expired: '로그인 시간이 만료되었습니다. 해당 봇의 로그인 버튼을 다시 눌러 주세요.',
  service_unavailable_check_docker_manager: '관리 서비스에 연결하지 못했습니다. Docker Manager에서 broker 상태를 확인해 주세요.',
};
function message(text, bad=false) { $('message').textContent=text; $('message').className=bad?'error':''; $('message').hidden=false; }
async function api(path, body={}) {
  const response = await fetch('/api/'+path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), credentials:'same-origin'});
  if (response.ok && response.headers.get('Content-Type')?.startsWith('application/zip')) return response.blob();
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(errors[data.error] || '처리하지 못했습니다: '+(data.error || response.status));
  return data;
}
function action(id, fn, event='click') {
  $(id).addEventListener(event, async e => {e.preventDefault(); const button=e.submitter || (e.currentTarget.tagName==='BUTTON'?e.currentTarget:null); if(button) button.disabled=true;
    try {await fn(e);} catch(error){message(error.message,true);} finally{if(button)button.disabled=false;}
  });
}
async function enter() {
  $('loginPanel').hidden=true; $('workspace').hidden=false; $('logout').hidden=false;
  await refresh();
  if(!configured) await discover();
}
async function discover() {
  const data=await api('discover'); $('relayChoices').replaceChildren();
  if(data.relays.length===1){fillRelay(data.relays[0]);if(data.relays[0].membership_required)message('기존 Relay를 찾았습니다. 주소와 소유자 공개키를 확인하고 연결해 주세요.');}
  else if(!data.relays.length)message('자동으로 찾지 못했습니다. 기존 Relay 주소와 소유자 공개키만 입력해 주세요.');
  else for(const relay of data.relays){const b=document.createElement('button');b.className='secondary';b.textContent=relay.relay;b.onclick=()=>fillRelay(relay);$('relayChoices').append(b);}
}
function fillRelay(record){$('relay').value=record.relay;$('owner').value=record.owner;if(!record.membership_required)message('이 Relay의 멤버십 제한을 자동 확인하지 못했습니다. 기존 Buzz 설치 설정을 확인해 주세요.',true);}
function statusName(status){return ({needs_login:'계정 로그인 필요',ready:'시작 준비',running:'실행 중',stopped:'중지됨',held:'보호 정책으로 대기',unknown:'상태 확인 필요'})[status]||status;}
async function refresh(){
  const data=await api('status');configured=data.configured;
  $('download').disabled=!configured;$('relayBadge').textContent=configured?'연결됨':'연결 대기';$('step1').classList.toggle('done',configured);
  if(configured){$('relay').value=data.relay;$('owner').value=data.owner;}
  for(const id of ['relay','owner'])$(id).readOnly=configured;
  $('saveRelay').hidden=configured;$('discover').hidden=configured;
  $('bots').replaceChildren();const selected=$('scheduleBot').value;$('scheduleBot').replaceChildren();
  if(!data.bots.length){const p=document.createElement('p');p.className='empty';p.textContent='Windows Buzz에서 봇을 만들고 배포하면 여기에 표시됩니다.';$('bots').append(p);}
  for(const bot of data.bots){const card=document.createElement('div');card.className='bot';const details=document.createElement('div');const name=document.createElement('strong');name.textContent=bot.name;const sub=document.createElement('small');sub.textContent=(bot.provider==='codex'?'Codex':'Claude Code')+' · '+bot.pubkey.slice(0,12)+'…';details.append(name,sub);const state=document.createElement('span');state.className='state';state.textContent=statusName(bot.status);const button=document.createElement('button');button.className='secondary';button.textContent='계정 로그인';button.disabled=bot.status==='running'||!bot.container_running||Boolean(authSession);button.onclick=async()=>{button.disabled=true;try{await startLogin(bot);}catch(e){message(e.message,true);button.disabled=false;}};card.append(details,state,button);$('bots').append(card);const option=document.createElement('option');option.value=bot.pubkey;option.textContent=bot.name;$('scheduleBot').append(option);}
  if(selected)$('scheduleBot').value=selected;
  const devices=await api('devices');$('devices').replaceChildren();$('step2').classList.toggle('done',devices.devices.length>0);
  for(const device of devices.devices){const row=document.createElement('div'),name=document.createElement('span'),button=document.createElement('button');name.textContent=device.name;button.className='quiet';button.textContent='연결 해제';button.onclick=async()=>{if(!confirm('이 Windows 연결 권한을 해제할까요? VPS의 실행 중인 봇은 유지됩니다.'))return;try{await api('revoke',{id:device.id});await refresh();}catch(e){message(e.message,true);}};row.append(name,button);$('devices').append(row);}
}
async function startLogin(bot){if(authSession)throw new Error('현재 로그인 세션을 먼저 마치거나 중지해 주세요.');const result=await api('auth/start',{pubkey:bot.pubkey});authSession=result.session;$('authTitle').textContent=bot.name+' · 공식 로그인';$('authPanel').hidden=false;$('authForm').hidden=false;$('cancelAuth').hidden=false;$('terminal').textContent='VPS에서 공식 로그인을 시작하고 있습니다…';$('authStatus').textContent='최대 10분 동안 진행됩니다.';$('authLinks').replaceChildren();$('authPanel').scrollIntoView({behavior:'smooth',block:'center'});}
function officialLinks(text){const hosts=['auth.openai.com','chatgpt.com','claude.ai','console.anthropic.com','platform.claude.com'];$('authLinks').replaceChildren();for(const raw of new Set(text.match(/https:\/\/[^\s<>"\x1b]+/g)||[])){try{const u=new URL(raw);if(!hosts.includes(u.hostname)||u.username||u.password)continue;const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='공식 로그인 열기 ↗ ('+u.hostname+')';$('authLinks').append(a);}catch{}}}
async function poll(){if(pollBusy||$('workspace').hidden||document.hidden)return;pollBusy=true;try{if(authSession){const data=await api('auth/poll',{session:authSession});const text=data.output.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g,'').replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g,'');$('terminal').textContent=text;officialLinks(text);if(data.done){authSession=null;$('authForm').hidden=true;$('cancelAuth').hidden=true;$('authStatus').textContent=data.success?'공식 로그인 명령이 완료되었습니다. Buzz에서 실제 답변을 확인하세요.':'로그인이 완료되지 않았습니다. 위 안내를 확인하고 다시 시도하세요.';await refresh();}}else if(++tick%3===0)await refresh();}catch(e){message(e.message,true);}finally{pollBusy=false;}}
action('loginForm',async()=>{await api('login',{setup_code:$('setupCode').value,password:$('password').value});$('setupCode').value='';$('password').value='';$('message').hidden=true;await enter();},'submit');
action('relayForm',async()=>{await api('configure',{relay:$('relay').value.trim(),owner:$('owner').value.trim()});message('Relay 연결 설정을 저장했습니다. 이제 Windows 연결 파일을 받으세요.');await refresh();},'submit');
action('discover',discover);action('refresh',refresh);
action('download',async()=>{const blob=await api('pair/bundle'),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Buzz-Windows-Connect.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);message('압축을 풀고 Buzz-VPS-Connect.exe를 실행해 주세요. 연결 파일은 10분 후 만료됩니다.');});
action('authForm',async()=>{if(!authSession)return;const input=$('authInput').value;$('authInput').value='';await api('auth/input',{session:authSession,text:input});},'submit');
action('cancelAuth',async()=>{if(authSession)await api('auth/cancel',{session:authSession});authSession=null;$('authForm').hidden=true;$('cancelAuth').hidden=true;$('terminal').textContent='';$('authLinks').replaceChildren();$('authStatus').textContent='로그인 세션을 중지했습니다.';await refresh();});
action('scheduleInit',async()=>{const result=await api('schedule/init');$('schedulerKey').textContent=result.pubkey;});
action('scheduleForm',async()=>{await api('schedule/save',{schedule:{channel_id:$('channel').value.trim(),bot_pubkey:$('scheduleBot').value,prompt:$('prompt').value,time:$('scheduleTime').value,membership_confirmed:$('membership').checked}});message('매일 예약을 저장했습니다. 메시지 전달과 AI 작업 완료를 실제로 확인하세요.');},'submit');
action('scheduleDisable',async()=>{await api('schedule/disable');message('예약을 중지했습니다. 이미 실행 중인 AI 작업은 취소되지 않습니다.');});
action('logout',async()=>{if(authSession)await api('auth/cancel',{session:authSession});await api('logout');location.reload();});
async function boot(){try{const response=await fetch('/api/hello');const hello=await response.json();if(!response.ok||!hello.ok)throw new Error(errors[hello.error]||'HTTPS 접속 주소를 확인해 주세요.');if(hello.claimed){$('setupCodeField').hidden=true;$('passwordLabel').textContent='설정 화면 비밀번호';$('password').autocomplete='current-password';$('passwordHint').textContent='처음 연결할 때 정한 비밀번호를 입력하세요.';}if(hello.authenticated)await enter();}catch(e){message(e.message,true);}}
boot();setInterval(poll,2000);
