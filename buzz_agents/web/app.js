'use strict';
const {t} = window.BuzzI18n;
window.BuzzI18n.translatePage();
const $ = id => document.getElementById(id);
let configured = false, authSession = null, pollBusy = false, tick = 0;
let pendingPairing = null, knownDevices = new Set();
let requestQueue = Promise.resolve(), initializing = false;
function queuedRequest(fn) {
  const result=requestQueue.then(fn);requestQueue=result.catch(()=>{});return result;
}
const errors = {
  invalid_or_expired_setup_code: t('최초 설정 코드가 틀리거나 만료되었습니다. Docker Manager에서 buzz-agents 오른쪽 ⋮ → 다시 시작을 선택한 뒤 portal의 최신 로그에서 새 코드를 복사하세요.'),
  invalid_or_expired_recovery_code: t('복구 코드가 틀리거나 만료·사용되었습니다. portal 터미널에서 복구 명령을 다시 실행하고 최신 로그를 확인하세요.'),
  pairing_expired_or_used: t('연결 파일이 만료되었거나 이미 사용되었습니다. 새 연결 파일을 받아 주세요.'),
  pairing_limit_revoke_old_connections: t('연결 한도에 도달했습니다. 사용하지 않는 Windows 연결을 해제하세요. 미사용 연결 파일은 10분 후 만료됩니다.'),
  invalid_settings_password: t('설정 화면 비밀번호가 맞지 않습니다.'),
  settings_password_minimum_12_characters: t('설정 화면 비밀번호는 12자 이상이어야 합니다.'),
  settings_login_required: t('설정 화면에 다시 로그인해 주세요.'),
  try_again_in_one_minute: t('요청이 많습니다. 1분 후 다시 시도해 주세요.'),
  configure_relay_first: t('먼저 내 Relay를 연결해 주세요.'),
  existing_relay_configuration_preserved: t('이미 연결된 Relay 설정은 자동으로 변경하지 않습니다.'),
  connection_program_not_packaged: t('Windows 연결 프로그램이 아직 이미지에 포함되지 않았습니다.'),
  stop_bot_before_authentication: t('실행 중인 봇을 Buzz에서 중지한 뒤 로그인해 주세요.'),
  existing_installation_requires_migration: t('이전 설치 데이터가 있습니다. 자동으로 덮어쓰지 않습니다.'),
  login_session_expired: t('로그인 시간이 만료되었습니다. 해당 봇의 로그인 버튼을 다시 눌러 주세요.'),
  service_unavailable_check_docker_manager: t('관리 서비스에 연결하지 못했습니다. Docker Manager에서 broker 상태를 확인해 주세요.'),
};
function message(text, bad=false) { $('message').textContent=text; $('message').className=bad?'error':''; $('message').hidden=false; }
async function api(path, body={}) {
  const result=await queuedRequest(async()=>{
    const retryable=['status','devices','discover'].includes(path);
    for(let attempt=0;;attempt++) {
      let response;
      try {
        response=await fetch('/api/'+path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), credentials:'same-origin'});
      } catch {
        if(retryable && attempt<2){await new Promise(resolve=>setTimeout(resolve,300*(attempt+1)));continue;}
        throw new Error(t('서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요.'));
      }
      if([502,503,504].includes(response.status)) {
        await response.arrayBuffer();
        if(retryable && attempt<2){await new Promise(resolve=>setTimeout(resolve,300*(attempt+1)));continue;}
        throw new Error(t('서버 연결이 일시적으로 원활하지 않습니다. 잠시 후 다시 시도하세요.'));
      }
      if(response.ok && response.headers.get('Content-Type')?.startsWith('application/zip'))return {blob:await response.blob()};
      let data;
      try {data=await response.json();} catch {throw new Error(t('서버에서 올바른 응답을 받지 못했습니다. 잠시 후 다시 시도하세요.'));}
      if(!data || typeof data!=='object')throw new Error(t('서버에서 올바른 응답을 받지 못했습니다. 잠시 후 다시 시도하세요.'));
      return {response,data};
    }
  });
  if(result.blob)return result.blob;
  const {response,data}=result;
  if (response.status===401 && data.error==='settings_login_required') {authSession=null;$('workspace').hidden=true;$('logout').hidden=true;$('loginPanel').hidden=false;await boot();}
  if (!response.ok || !data.ok) throw new Error(errors[data.error] || t('처리하지 못했습니다: ')+(data.error || response.status));
  return data;
}
// Guide images share the API queue so retained two-slot bridges never receive
// an unbounded browser image burst. No credentials or writes are retried here.
function loadGuide() {
  for(const img of document.querySelectorAll('#buzzGuide img[data-src]')) {
    if(img.dataset.queued)continue;
    img.dataset.queued='true';
    queuedRequest(()=>new Promise(resolve=>{
      let timer;
      const finish=()=>{clearTimeout(timer);img.onload=null;img.onerror=null;delete img.dataset.queued;resolve();};
      img.onload=()=>{delete img.dataset.src;finish();};
      img.onerror=finish;
      timer=setTimeout(()=>{img.removeAttribute('src');finish();},15000);
      img.loading='eager';img.src=img.dataset.src;
    }));
  }
}
function action(id, fn, event='click') {
  $(id).addEventListener(event, async e => {e.preventDefault(); const button=e.submitter || (e.currentTarget.tagName==='BUTTON'?e.currentTarget:null); if(button) button.disabled=true;
    try {await fn(e);} catch(error){message(error.message,true);} finally{if(button)button.disabled=false;}
  });
}
function recoveryMode(show) { $('loginForm').hidden=show; $('recoveryForm').hidden=!show; $('showRecovery').hidden=show; }

async function enter() {
  if(initializing)return;
  initializing=true;$('retryStartup').hidden=true;
  $('message').hidden=true;
  $('loginPanel').hidden=true;$('workspace').hidden=true;$('logout').hidden=false;
  try {
    await refresh();
    if(!configured) await discover();
    $('workspace').hidden=false;
    loadGuide();
  } catch(error) {
    $('retryStartup').hidden=false;
    throw error;
  } finally {
    if($('loginPanel').hidden)$('workspace').hidden=false;
    initializing=false;
  }
}
async function discover() {
  const data=await api('discover'); $('relayChoices').replaceChildren();
  if(data.relays.length===1){fillRelay(data.relays[0]);if(data.relays[0].membership_required)message(t('기존 Relay를 찾았습니다. 주소와 소유자 공개키를 확인하고 연결해 주세요.'));}
  else if(!data.relays.length)message(t('자동으로 찾지 못했습니다. 기존 Relay 주소와 소유자 공개키만 입력해 주세요.'));
  else for(const relay of data.relays){const b=document.createElement('button');b.className='secondary';b.textContent=relay.relay;b.onclick=()=>fillRelay(relay);$('relayChoices').append(b);}
}
function fillRelay(record){$('relay').value=record.relay;$('owner').value=record.owner;if(!record.membership_required)message(t('이 Relay의 멤버십 제한을 자동 확인하지 못했습니다. 기존 Buzz 설치 설정을 확인해 주세요.'),true);}
function statusName(status){return ({needs_login:t('계정 로그인 필요'),ready:t('시작 준비'),running:t('실행 중'),stopped:t('중지됨'),held:t('보호 정책으로 대기'),unknown:t('상태 확인 필요')})[status]||status;}
async function refresh(){
  const data=await api('status');configured=data.configured;
  $('download').disabled=!configured;$('relayBadge').textContent=configured?t('연결됨'):t('연결 대기');$('step1').classList.toggle('done',configured);
  if(configured){$('relay').value=data.relay;$('owner').value=data.owner;}
  $('communityRelay').value=configured?data.relay:'';
  $('copyCommunityRelay').disabled=!configured;
  for(const id of ['relay','owner'])$(id).readOnly=configured;
  $('saveRelay').hidden=configured;$('discover').hidden=configured;
  $('bots').replaceChildren();const selected=$('scheduleBot').value;$('scheduleBot').replaceChildren();
  if(!data.bots.length){const p=document.createElement('p');p.className='empty';p.textContent=t('Windows Buzz에서 봇을 만들고 배포하면 여기에 표시됩니다.');$('bots').append(p);}
  for(const bot of data.bots){const card=document.createElement('div');card.className='bot';const details=document.createElement('div');const name=document.createElement('strong');name.textContent=bot.name;const sub=document.createElement('small');sub.textContent=(bot.provider==='codex'?'Codex':'Claude Code')+' · '+bot.pubkey.slice(0,12)+'…';details.append(name,sub);const state=document.createElement('span');state.className='state';state.textContent=statusName(bot.status);const button=document.createElement('button');button.className='secondary';button.textContent=t('계정 로그인');button.disabled=bot.status==='running'||!bot.container_running||Boolean(authSession);button.onclick=async()=>{button.disabled=true;try{await startLogin(bot);}catch(e){message(e.message,true);button.disabled=false;}};card.append(details,state,button);$('bots').append(card);const option=document.createElement('option');option.value=bot.pubkey;option.textContent=bot.name;$('scheduleBot').append(option);}
  if(selected)$('scheduleBot').value=selected;
  const devices=await api('devices');$('devices').replaceChildren();$('step2').classList.toggle('done',devices.devices.length>0);
  knownDevices=new Set(devices.devices.map(d=>d.id));
  if(pendingPairing && devices.devices.some(d=>!pendingPairing.ids.has(d.id))){pendingPairing=null;$('connectionHint').textContent=t('서버에 Windows 연결이 등록되었습니다. 연결 프로그램의 저장 완료 메시지도 확인하세요. 연결 완료 후에는 파일의 10분 제한이 적용되지 않습니다.');message(t('Windows 연결이 서버에 등록되었습니다. 프로그램에서 저장 완료를 확인한 뒤 Buzz를 다시 실행하세요.'));}
  else if(pendingPairing && Date.now()>=pendingPairing.deadline){pendingPairing=null;message(t('연결 파일의 10분 유효시간이 지났습니다. 아직 연결하지 못했다면 새 연결 파일을 받으세요.'),true);}
  $('download').textContent=devices.devices.length||pendingPairing?t('새 Windows 연결 파일 받기 ↓'):t('Windows 연결 파일 받기 ↓');
  for(const device of devices.devices){const row=document.createElement('div'),name=document.createElement('span'),button=document.createElement('button');name.textContent=device.name+' · ID '+device.id;button.className='quiet';button.textContent=t('연결 해제');button.onclick=async()=>{if(!confirm(t('이 Windows 연결 권한을 해제할까요? VPS의 실행 중인 봇은 유지됩니다.')))return;try{await api('revoke',{id:device.id});await refresh();}catch(e){message(e.message,true);}};row.append(name,button);$('devices').append(row);}
}
async function startLogin(bot){if(authSession)throw new Error(t('현재 로그인 세션을 먼저 마치거나 중지해 주세요.'));const result=await api('auth/start',{pubkey:bot.pubkey});authSession=result.session;$('authTitle').textContent=bot.name+t(' · 공식 로그인');$('authPanel').hidden=false;$('authForm').hidden=false;$('cancelAuth').hidden=false;$('terminal').textContent=t('VPS에서 공식 로그인을 시작하고 있습니다…');$('authStatus').textContent=t('최대 10분 동안 진행됩니다.');$('authLinks').replaceChildren();$('authPanel').scrollIntoView({behavior:'smooth',block:'center'});}
function officialLinks(text){const hosts=['auth.openai.com','chatgpt.com','claude.ai','console.anthropic.com','platform.claude.com'];$('authLinks').replaceChildren();for(const raw of new Set(text.match(/https:\/\/[^\s<>"\x1b]+/g)||[])){try{const u=new URL(raw);if(!hosts.includes(u.hostname)||u.username||u.password)continue;const a=document.createElement('a');a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent=t('공식 로그인 열기 ↗ (')+u.hostname+')';$('authLinks').append(a);}catch{}}}
async function poll(){if(initializing||pollBusy||$('workspace').hidden||document.hidden)return;pollBusy=true;try{if(authSession){const data=await api('auth/poll',{session:authSession});const text=data.output.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g,'').replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g,'');$('terminal').textContent=text;officialLinks(text);if(data.done){authSession=null;$('authForm').hidden=true;$('cancelAuth').hidden=true;$('authStatus').textContent=data.success?t('공식 로그인 명령이 완료되었습니다. Buzz에서 실제 답변을 확인하세요.'):t('로그인이 완료되지 않았습니다. 위 안내를 확인하고 다시 시도하세요.');await refresh();}}else if(++tick%3===0)await refresh();}catch(e){message(e.message,true);}finally{pollBusy=false;}}
action('loginForm',async()=>{await api('login',{setup_code:$('setupCode').value,password:$('password').value});$('setupCode').value='';$('password').value='';$('message').hidden=true;await enter();},'submit');
action('showRecovery',()=>recoveryMode(true));
action('cancelRecovery',()=>{$('recoveryCode').value='';$('recoveryPassword').value='';recoveryMode(false);});
action('recoveryForm',async()=>{await api('recover',{recovery_code:$('recoveryCode').value,password:$('recoveryPassword').value});$('recoveryCode').value='';$('recoveryPassword').value='';$('password').value='';recoveryMode(false);message(t('비밀번호를 다시 설정했습니다. 새 비밀번호로 로그인하세요. 봇과 Windows 연결은 유지됩니다.'));},'submit');
action('relayForm',async()=>{await api('configure',{relay:$('relay').value.trim(),owner:$('owner').value.trim()});message(t('Relay 연결 설정을 저장했습니다. 이제 Windows 연결 파일을 받으세요.'));await refresh();},'submit');
action('discover',discover);action('refresh',refresh);
action('retryStartup',enter);
action('download',async()=>{const ids=new Set(knownDevices),blob=await api('pair/bundle');pendingPairing={ids,deadline:Date.now()+600000};const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Buzz-Windows-Connect.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);message(t('압축을 풀고 Buzz-VPS-Connect.exe를 실행해 주세요. 연결 파일은 10분 후 만료됩니다.'));});
action('authForm',async()=>{if(!authSession)return;const input=$('authInput').value;$('authInput').value='';await api('auth/input',{session:authSession,text:input});},'submit');
action('cancelAuth',async()=>{if(authSession)await api('auth/cancel',{session:authSession});authSession=null;$('authForm').hidden=true;$('cancelAuth').hidden=true;$('terminal').textContent='';$('authLinks').replaceChildren();$('authStatus').textContent=t('로그인 세션을 중지했습니다.');await refresh();});
action('scheduleInit',async()=>{const result=await api('schedule/init');$('schedulerKey').textContent=result.pubkey;});
action('scheduleForm',async()=>{await api('schedule/save',{schedule:{channel_id:$('channel').value.trim(),bot_pubkey:$('scheduleBot').value,prompt:$('prompt').value,time:$('scheduleTime').value,membership_confirmed:$('membership').checked}});message(t('매일 예약을 저장했습니다. 메시지 전달과 AI 작업 완료를 실제로 확인하세요.'));},'submit');
action('scheduleDisable',async()=>{await api('schedule/disable');message(t('예약을 중지했습니다. 이미 실행 중인 AI 작업은 취소되지 않습니다.'));});
action('logout',async()=>{if(authSession)await api('auth/cancel',{session:authSession});await api('logout');location.reload();});
// Fragments never enter HTTP/access logs. Scrub before the first asynchronous request.
function takeAccessFragment() {
  if (!location.hash) return null;
  const params=new URLSearchParams(location.hash.slice(1));
  history.replaceState(null,'',location.pathname+location.search);
  const keys=[...params.keys()];
  if(keys.length!==1 || !['setup_code','recovery_code'].includes(keys[0]) || !/^[A-Za-z0-9_-]{32,100}$/.test(params.get(keys[0]))) {
    message(t('설정 링크의 인증값을 읽지 못했습니다. 아래 로그 안내에 따라 최신 코드를 직접 입력하세요.'),true);return null;
  }
  return {kind:keys[0],value:params.get(keys[0])};
}
let accessFragment=takeAccessFragment();
async function boot(){try{
  const response=await fetch('/api/hello');const hello=await response.json();
  if(!response.ok||!hello.ok)throw new Error(errors[hello.error]||t('HTTPS 접속 주소를 확인해 주세요.'));
  if(hello.claimed){$('setupCodeField').hidden=true;$('setupCode').value='';$('showRecovery').hidden=false;$('passwordLabel').textContent=t('설정 화면 비밀번호');$('password').autocomplete='current-password';$('passwordHint').textContent=t('처음 연결할 때 정한 비밀번호를 입력하세요. 재시작 후에도 같은 비밀번호입니다.');}
  if(accessFragment){
    if(accessFragment.kind==='setup_code'&&!hello.claimed){$('setupCode').value=accessFragment.value;message(t('링크의 설정 코드를 입력했습니다. 새 비밀번호를 정하고 설정 시작을 누르세요.'));}
    else if(accessFragment.kind==='recovery_code'&&hello.claimed){$('workspace').hidden=true;$('loginPanel').hidden=false;recoveryMode(true);$('recoveryCode').value=accessFragment.value;message(t('복구 코드를 입력했습니다. 새 비밀번호를 정해 주세요.'));}
    else message(hello.claimed?t('이미 설정된 서버입니다. 기존 비밀번호로 로그인하세요.'):t('아직 최초 설정 전입니다. 최신 setup code로 시작하세요.'));
    accessFragment=null;
  }
  $('startupNote').hidden=true;$('loginSubmit').disabled=false;
  if(hello.authenticated&&$('recoveryForm').hidden)await enter();
}catch(e){message(e.message,true);}}
window.addEventListener('hashchange',()=>{accessFragment=takeAccessFragment();if(accessFragment)boot();});
boot();setInterval(poll,2000);

action('copyCommunityRelay', async()=>{
  const field=$('communityRelay');
  if(!configured || !field.value)return;
  try {
    await navigator.clipboard.writeText(field.value);
    $('relayCopyStatus').textContent=t('주소를 복사했습니다. Windows Buzz의 주소 입력란에 붙여넣으세요.');
  } catch {
    field.focus();field.select();
    $('relayCopyStatus').textContent=t('자동 복사를 사용할 수 없습니다. 선택된 주소를 Ctrl+C로 복사하세요.');
  }
});
