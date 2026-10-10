'use strict';
const {t} = window.BuzzI18n;
window.BuzzI18n.translatePage();
const $ = id => document.getElementById(id);
let configured = false, authSession = null, pollBusy = false, tick = 0;
let updatePlan = null, updateBusy = false;
let pendingPairing = null, knownDevices = new Set();
let requestQueue = Promise.resolve(), initializing = false;
function queuedRequest(fn) {
  const result=requestQueue.then(fn);requestQueue=result.catch(()=>{});return result;
}
const errors = {
  bot_update_busy: t('다른 업데이트나 배포가 진행 중입니다. 완료 후 다시 시도하세요.'),
  bot_update_preview_changed: t('봇 설정이 변경되었습니다. 업데이트 창을 닫고 다시 열어 확인하세요.'),
  authentication_already_in_progress: t('공식 계정 로그인이 진행 중입니다. 먼저 로그인을 마치거나 취소하세요.'),
  deployment_image_mismatch: t('새 컨테이너의 실행 이미지를 확인하지 못했습니다. 현재 상태와 broker 로그를 확인하세요.'),
  bot_update_stop_unconfirmed: t('봇 중지를 확인하지 못해 업데이트를 중단했습니다. 현재 상태를 확인하세요.'),

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
  if (data.error==='login_session_expired' && ['auth/poll','auth/input','auth/cancel'].includes(path)) {
    if(authSession===body.session) {
      authSession=null;
      $('authForm').hidden=true;$('cancelAuth').hidden=true;
      $('authInput').value='';$('terminal').textContent='';$('authLinks').replaceChildren();
      $('authStatus').textContent=errors.login_session_expired;
    }
    // Cancellation of an already absent session is complete, including logout.
    if(path==='auth/cancel')return {ok:true,expired:true};
  }
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
function botHealth(bot){
  const messages={
    runtime_budget_wait:t('설정한 작업 시작 한도에 도달했습니다. 시간이 지나면 새 요청을 받을 수 있습니다. 계속 작업하려면 봇 설정의 횟수 한도를 0으로 변경한 뒤 재배포하세요.'),
    runtime_worker_deadline:t('한 작업이 최대 시간과 정리 대기 시간을 초과했습니다. 해당 작업만 중단했습니다. Harness Log에서 재시도 결과를 확인하세요.'),
    runtime_frame_too_large:t('메시지가 공식 실행기의 10MB 한도를 초과했습니다. 이미지나 첨부 내용을 나누어 다시 요청하세요.'),
    runtime_frame_invalid_json:t('실행기에서 올바르지 않은 메시지를 받았습니다. Harness Log와 실행기 버전을 확인하세요.'),
    runtime_frame_invalid_shape:t('실행기의 메시지 형식이 올바르지 않습니다. Harness Log를 확인하세요.'),
    runtime_transport_failed:t('실행기와의 통신이 끊겼습니다. Harness Log에서 재시도 결과를 확인하세요.'),
    runtime_output_backpressure:t('실행기가 메시지를 제때 받지 못해 연결을 중단했습니다. Harness Log를 확인하세요.'),
    runtime_adapter_cleanup_failed:t('이전 작업의 종료를 확인하지 못해 봇을 보류했습니다. 로그를 확인한 뒤 봇을 중지하고 다시 배포하세요.'),
    runtime_process_limit:t('프로세스·스레드 한도에 도달했습니다. 봇을 중지한 뒤 최신 버전으로 재배포하세요. 반복되면 동시 실행 수를 줄여 주세요.'),
    runtime_process_creation_failed:t('새 프로세스를 만들지 못했습니다. 자원 사용량과 로그를 확인하세요.'),
    runtime_approval_review_failed:t('자동 승인 검토가 실패했습니다. 자원 상태와 Harness Log를 확인하세요.'),
    runtime_process_limit_near_capacity:t('프로세스·스레드 사용량이 한도에 가깝습니다. 동시 실행 수를 확인하세요.')
  };
  const resources=bot.resources||{};
  const code=bot.reason==='worker_cleanup_timeout'?'runtime_adapter_cleanup_failed':bot.diagnostic||resources.health_warning;
  const parts=[];
  if(messages[code])parts.push(messages[code]);
  else if(bot.diagnostic)parts.push(t('실행 오류가 기록되었습니다. Harness Log를 확인하세요.'));
  if(Number.isSafeInteger(resources.pids_current)&&Number.isSafeInteger(resources.pids_max))parts.push(t('최근 프로세스·스레드 사용량')+': '+resources.pids_current+' / '+resources.pids_max);
  return parts.join(' ');
}
async function refresh(){
  const data=await api('status');configured=data.configured;
  $('download').disabled=!configured;$('relayBadge').textContent=configured?t('연결됨'):t('연결 대기');$('step1').classList.toggle('done',configured);
  if(configured){$('relay').value=data.relay;$('owner').value=data.owner;}
  $('communityRelay').value=configured?data.relay:'';
  $('mobilePairingStatus').textContent=t(data.mobile_pairing?.state==='available'?"페어링 연결 경로를 확인했습니다. 휴대폰 연결 완료는 직접 확인해 주세요.":configured?"페어링 자동 설정을 확인해야 합니다. 먼저 Try again을 누르고, 계속 실패하면 위의 다시 시작 안내를 따라 주세요. 반복되면 broker 로그의 Mobile pairing 항목을 확인하세요.":"내 Relay 설정을 저장하면 휴대폰 페어링을 자동으로 준비합니다.");
  $('copyCommunityRelay').disabled=!configured;
  for(const id of ['relay','owner'])$(id).readOnly=configured;
  $('saveRelay').hidden=configured;$('discover').hidden=configured;
  $('bots').replaceChildren();const selected=$('scheduleBot').value;$('scheduleBot').replaceChildren();
  if(!data.bots.length){const p=document.createElement('p');p.className='empty';p.textContent=t('Windows Buzz에서 봇을 만들고 배포하면 여기에 표시됩니다.');$('bots').append(p);}
  for(const bot of data.bots){const card=document.createElement('div');card.className='bot';const details=document.createElement('div');const name=document.createElement('strong');name.textContent=bot.name;const sub=document.createElement('small');sub.textContent=(bot.provider==='codex'?'Codex':'Claude Code')+' · '+bot.pubkey.slice(0,12)+'…';details.append(name,sub);const health=botHealth(bot);if(health){const info=document.createElement('small');info.textContent=health;details.append(info);}const state=document.createElement('span');state.className='state';state.textContent=statusName(bot.status);const button=document.createElement('button');button.className='secondary';button.textContent=t('계정 로그인');button.disabled=bot.status==='running'||!bot.container_running||Boolean(authSession);button.onclick=async()=>{button.disabled=true;try{await startLogin(bot);}catch(e){message(e.message,true);button.disabled=false;}};const actions=document.createElement('div');actions.className='bot-actions';const updateButton=document.createElement('button');updateButton.className='secondary update-bot';updateButton.textContent=t('업데이트·다시 시작');updateButton.disabled=Boolean(authSession)||data.update?.state==='running';updateButton.onclick=()=>openUpdate(bot).catch(e=>message(e.message,true));button.disabled=button.disabled||data.update?.state==='running';actions.append(button,updateButton);card.append(details,state,actions);$('bots').append(card);const option=document.createElement('option');option.value=bot.pubkey;option.textContent=bot.name;$('scheduleBot').append(option);}
  if(selected)$('scheduleBot').value=selected;
  renderUpdateStatus(data.update);
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
action('cancelAuth',async()=>{const result=authSession?await api('auth/cancel',{session:authSession}):null;authSession=null;$('authForm').hidden=true;$('cancelAuth').hidden=true;$('authInput').value='';$('terminal').textContent='';$('authLinks').replaceChildren();$('authStatus').textContent=result?.expired?errors.login_session_expired:t('로그인 세션을 중지했습니다.');await refresh();});
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

// Guide navigation is explanatory only: visiting a tab never marks setup done.
const guideTabs=[...document.querySelectorAll('#buzzGuide [role="tab"]')];
let guideIndex=0;
function showGuideStep(index, focus=false, scroll=false) {
  guideIndex=Math.max(0,Math.min(guideTabs.length-1,index));
  guideTabs.forEach((tab,i)=>{
    const active=i===guideIndex;
    tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
    $(tab.getAttribute('aria-controls')).hidden=!active;
  });
  $('guidePrev').disabled=guideIndex===0;
  $('guideNext').disabled=guideIndex===guideTabs.length-1;
  $('guideProgress').textContent=(guideIndex+1)+' / '+guideTabs.length;
  if(focus)guideTabs[guideIndex].focus({preventScroll:true});
  if(scroll)document.querySelector('.guide-tabs').scrollIntoView({block:'start'});
}
guideTabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>showGuideStep(index));
  tab.addEventListener('keydown',event=>{
    let next;
    if(event.key==='ArrowRight')next=(index+1)%guideTabs.length;
    else if(event.key==='ArrowLeft')next=(index+guideTabs.length-1)%guideTabs.length;
    else if(event.key==='Home')next=0;
    else if(event.key==='End')next=guideTabs.length-1;
    else return;
    event.preventDefault();showGuideStep(next,true);
  });
});
$('guidePrev').addEventListener('click',()=>showGuideStep(guideIndex-1,true,true));
$('guideNext').addEventListener('click',()=>showGuideStep(guideIndex+1,true,true));

function renderUpdateStatus(job){
  const el=$('updateStatus');el.hidden=!job?.state;
  if(!job?.state)return;
  const descriptions={running:t('봇 업데이트 중입니다. 창을 닫아도 서버에서 계속 진행됩니다.'),succeeded:t('봇 컨테이너 업데이트를 확인했습니다. 아래 상태와 Buzz의 실제 답변을 확인하세요. 로그인 필요로 표시되면 해당 봇에 로그인하세요.'),failed:t('업데이트를 완료하지 못했습니다. 기존 봇을 삭제하지 말고 오류와 현재 상태를 확인하세요.'),interrupted:t('업데이트 도중 관리 서비스가 재시작되어 완료 여부를 확인할 수 없습니다. 현재 상태를 확인한 뒤 다시 시도하세요.')};
  el.textContent=job.pubkey.slice(0,12)+'… · '+(descriptions[job.state]||'')+(job.error?'\n'+(errors[job.error]||job.error):'');
}
async function openUpdate(bot){
  if(authSession||updateBusy)return;
  const plan=await api('bot/update-preview',{pubkey:bot.pubkey});
  updatePlan={...plan,request_id:crypto.randomUUID().replaceAll('-','')};
  $('updateBotName').textContent=plan.name+' · '+plan.pubkey.slice(0,12)+'…';
  $('updatePolicy').textContent=t('현재 실행 제한')+': '+plan.policy.turn_limit+' / '+plan.policy.window_seconds+'s · '+plan.policy.daily_limit+' / 24h · '+plan.policy.max_turn_seconds+'s';
  $('updateDefaults').checked=false;$('updateError').textContent='';$('updateDialog').showModal();
}
action('cancelUpdate',()=>{if(!updateBusy){$('updateDialog').close();updatePlan=null;}});
$('updateDialog').addEventListener('cancel',e=>{if(updateBusy)e.preventDefault();else updatePlan=null;});
action('updateForm',async()=>{
  if(!updatePlan||updateBusy)return;
  updateBusy=true;$('cancelUpdate').disabled=true;$('updateError').textContent='';
  try{
    const result=await api('bot/update',{pubkey:updatePlan.pubkey,revision:updatePlan.revision,request_id:updatePlan.request_id,use_defaults:$('updateDefaults').checked});
    renderUpdateStatus(result.update);$('updateDialog').close();updatePlan=null;await refresh();
  }catch(e){$('updateError').textContent=e.message+' '+t('응답을 받지 못했더라도 서버 작업은 진행됐을 수 있습니다. 창을 닫고 현재 상태를 확인하세요.');}
  finally{updateBusy=false;$('cancelUpdate').disabled=false;}
},'submit');
