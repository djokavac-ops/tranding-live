const $=id=>document.getElementById(id);let market={};const fmt=(n,d=2)=>Number.isFinite(Number(n))?Number(n).toLocaleString("de-DE",{maximumFractionDigits:d}):"—";const eur=n=>fmt(n)+" €";const sig=s=>"signal "+String(s||"WAIT").replaceAll(" ","");async function api(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(await r.text());return r.json()}async function settings(){const s=await api("/api/settings");Object.entries(s).forEach(([k,v])=>{if($(k))$(k).value=k==="auto_engine_enabled"?String(v):v});$("dbstatus").innerHTML=`<div class="metric"><span>Database</span><strong>${s.database_url_type}</strong></div><div class="metric"><span>Persistent</span><strong>${s.database_persistent?"DA":"NE"}</strong></div>`}async function save(){let p={};["account_size","daily_target","daily_max_loss","risk_per_trade_pct","max_trades_per_day","max_open_trades","min_confidence","min_risk_reward","engine_interval_seconds"].forEach(k=>p[k]=parseFloat($(k).value));p.auto_engine_enabled=$("auto_engine_enabled").value==="true";await api("/api/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});$("status").textContent="Sačuvano"}function card(x){return `<section class="card"><h3>${x.name}</h3><div class="${sig(x.signal)}">${x.signal}</div><p><b>AI Score:</b> ${x.ai_score}/100 · <b>Regime:</b> ${x.market_regime} · <b>Strategy:</b> ${x.strategy}</p><div class="ai">${x.ai_explanation||""}</div><div class="metric"><span>Trend / Momentum / Volume</span><strong>${fmt(x.trend_score)} / ${fmt(x.momentum_score)} / ${fmt(x.volume_score)}</strong></div><div class="metric"><span>Volatility / Risk / RR</span><strong>${fmt(x.volatility_score)} / ${fmt(x.risk_score)} / ${fmt(x.rr_score)}</strong></div><div class="metric"><span>Entry / SL / TP1</span><strong>${fmt(x.entry)} / ${fmt(x.stop)} / ${fmt(x.target1)}</strong></div></section>`}function render(){const f=$("filter").value;let vals=Object.values(market).filter(x=>!x.error&&(f==="ALL"||x.group===f));vals.sort((a,b)=>(b.ai_score||0)-(a.ai_score||0));let strong=vals.filter(x=>String(x.signal).startsWith("STRONG")).length,buys=vals.filter(x=>x.signal.includes("BUY")).length,sells=vals.filter(x=>x.signal.includes("SELL")).length,waits=vals.filter(x=>x.signal==="WAIT").length,avg=vals.length?Math.round(vals.reduce((s,x)=>s+(x.ai_score||0),0)/vals.length):0;$("summary").innerHTML=`<div class="pill"><b>${strong}</b><br>Strong</div><div class="pill"><b>${buys}</b><br>BUY</div><div class="pill"><b>${sells}</b><br>SELL</div><div class="pill"><b>${waits}</b><br>WAIT</div><div class="pill"><b>${avg}</b><br>Avg AI</div>`;$("best").innerHTML=vals[0]?card(vals[0]):"Nema podataka";$("cards").innerHTML=vals.map(card).join("")}async function loadMarket(){market=await api("/api/market");render()}async function loadBrief(){const b=await api("/api/ai/market-brief");$("aiBrief").innerHTML=(b.snapshots||[]).slice(0,3).map(r=>`<div class="log"><b>${r.best_signal} · ${r.best_name}</b><br>${r.market_comment}<br><span class="small">${r.ts}</span></div>`).join("")||"Još nema brief-a"}async function loadAudit(){const a=await api("/api/ai/audit");$("audit").innerHTML=(a.audit||[]).slice(0,8).map(r=>`<div class="log"><b>${r.decision} · ${r.name}</b><br>Score ${fmt(r.final_score)} · ${r.strategy} · ${r.market_regime}<br>Trend ${fmt(r.trend_score)} · Momentum ${fmt(r.momentum_score)} · Volume ${fmt(r.volume_score)} · Risk ${fmt(r.risk_score)}<br><span class="small">${r.ts}</span></div>`).join("")||"Nema audit-a"}function tradeHtml(t){return `<div class="trade"><b>${t.status} · ${t.side} ${t.name}</b><br>Entry ${fmt(t.entry)} · Current ${fmt(t.current_price)} · PnL ${eur(t.pnl)}<br>${t.ai_explanation||""}</div>`}async function loadPaper(){const p=await api("/api/paper/status");$("pnl").textContent=eur(p.daily_pnl);$("openTrades").innerHTML=p.open.map(tradeHtml).join("")||"Nema otvorenih";$("history").innerHTML=p.trades.map(tradeHtml).join("")||"Nema trejdova";$("engineLog").innerHTML=p.engine_runs.map(r=>`<div class="log"><b>${r.status}</b> · ${r.message}<br><span class="small">${r.ts}</span></div>`).join("")||"Nema logova"}async function run(){const r=await api("/api/paper/run-cycle",{method:"POST"});$("status").textContent=r.status;await refresh()}async function reset(){await api("/api/paper/reset-day",{method:"POST"});await refresh()}function reportHtml(r){return `<h2>${r.title}</h2><div class="summary"><div class="pill"><b>${r.total_trades}</b><br>Trejdova</div><div class="pill"><b>${r.win_rate}%</b><br>Win rate</div><div class="pill"><b>${eur(r.pnl)}</b><br>PnL</div><div class="pill"><b>${r.profit_factor}</b><br>PF</div><div class="pill"><b>${r.open_trades}</b><br>Open</div></div>`}async function showReport(type){const r=await api(type==="daily"?"/api/report/daily":type==="weekly"?"/api/report/weekly":"/api/report/all");$("report").classList.remove("hidden");$("report").innerHTML=reportHtml(r)}













async function loadIbkrExecution(){
  try{
    const s=await api("/api/ibkr-execution/status");
    const r=s.readiness||{};
    const pm=s.portfolio_manager||{};
    const sel=(pm.selected||[]).map(x=>`<div class="log"><b>${x.symbol} · ${x.name}</b><br>${x.signal} · Score ${fmt(x.score)} · Max position ${eur(x.max_position_eur)}<br>${x.reason}</div>`).join("") || "No selected opportunities now.";
    $("ibkrExecution").innerHTML=`<div class="metric"><span>Paper first</span><strong>${r.paper_first?"YES":"NO"}</strong></div><div class="metric"><span>Live locked</span><strong>${r.live_locked?"YES":"NO"}</strong></div><div class="metric"><span>Use Margin</span><strong>${r.use_margin?"ON":"OFF"}</strong></div><div class="metric"><span>IBKR Account ID</span><strong>${r.account_id||"not set"}</strong></div><div class="metric"><span>Max live position</span><strong>${eur(r.limits?.live_max_position_eur||25)}</strong></div><div class="ai">${r.next_step}</div><h3>Portfolio Manager</h3>${sel}`;
  }catch(e){$("ibkrExecution").innerHTML="IBKR Execution panel trenutno nije dostupan."}
}

async function loadHybridMode(){
  try{
    const h=await api("/api/hybrid/status");
    const rows=(h.items||[]).slice(0,8).map(x=>`<div class="log"><b>${x.hybrid.mode.toUpperCase()} · ${x.name}</b><br>${x.signal} · Score ${fmt(x.score)}<br>${x.hybrid.reason}</div>`).join("");
    $("hybridMode").innerHTML=`<div class="metric"><span>Enabled</span><strong>${h.settings.enabled?"YES":"NO"}</strong></div><div class="metric"><span>Auto / Approval / Idea</span><strong>${h.settings.auto_threshold} / ${h.settings.approval_threshold} / ${h.settings.idea_threshold}</strong></div><div class="ai">${h.explanation}</div>${rows}`;
  }catch(e){$("hybridMode").innerHTML="Hybrid mode trenutno nije dostupan."}
}

async function loadProfessional50(){
  try{
    const p=await api("/api/professional/status");
    const scan=(p.market_scanner?.top||[]).slice(0,5).map(x=>`<div class="log"><b>${x.symbol} · ${x.name}</b><br>${x.signal} · Rank ${fmt(x.scanner_rank_score)} · Committee ${x.committee_decision}</div>`).join("");
    const dt=(p.digital_twin?.simulations||[]).map(x=>`<div class="log"><b>${x.symbol}</b><br>${x.decision} · Risk after ${eur(x.risk_after)} · Size risk ${eur(x.sizing.risk_eur)}</div>`).join("");
    const drift=p.drift_detection||{};
    const cap=p.capital_manager||{};
    $("professionalCore").innerHTML=`<div class="metric"><span>Scenario Macro</span><strong>${p.scenario_engine?.macro?.regime||"—"}</strong></div><div class="metric"><span>Drift</span><strong>${drift.drift_detected?"YES":"NO"}</strong></div><div class="metric"><span>Cash Plan</span><strong>${fmt(cap.cash_pct)}%</strong></div><div class="ai"><b>Drift reasons:</b> ${(drift.reasons||[]).join("; ")}<br><b>Scenario:</b> ${p.scenario_engine?.message||""}</div><h3>Market Scanner</h3>${scan}<h3>Digital Twin</h3>${dt}`;
  }catch(e){$("professionalCore").innerHTML="Professional 5.0 Core trenutno nije dostupan."}
}

async function loadOilCfdEngine(){
  try{
    const r=await api("/api/cfd/watchlist");
    const oil=r.oil_macro||{};
    const rows=(r.results||[]).slice(0,6).map(x=>`<div class="log"><b>${x.action} · ${x.name}</b><br>CFD Score ${fmt(x.cfd_score)} · Base AI ${fmt(x.base_ai_score)} · Risk ${eur(x.risk_eur)}<br>Qty ${fmt(x.suggested_qty,4)} · Notional ${eur(x.estimated_notional)}<br>${x.explanation}</div>`).join("");
    $("oilCfdEngine").innerHTML=`<div class="metric"><span>Oil Macro</span><strong>${oil.signal||"—"}</strong></div><div class="metric"><span>Bull/Bear</span><strong>${oil.bullish_score||0} / ${oil.bearish_score||0}</strong></div><div class="ai">${oil.explanation||""}</div>${rows}`;
  }catch(e){$("oilCfdEngine").innerHTML="Oil/CFD engine trenutno nije dostupan."}
}
async function setOilBias(bias){await api(`/api/oil-macro/bias/${bias}`,{method:"POST"});$("status").textContent=`Macro bias: ${bias}`;await refresh()}

async function loadIntelligencePlus(){
  try{
    const [news,macro,shift,heat,health,perf]=await Promise.all([
      api("/api/news-intelligence/status"),
      api("/api/macro/regime-plus"),
      api("/api/regime-shift"),
      api("/api/portfolio/heat"),
      api("/api/health-monitor"),
      api("/api/performance/dashboard-plus")
    ]);
    $("intelligencePlus").innerHTML=`<div class="metric"><span>Macro Regime</span><strong>${macro.regime}</strong></div><div class="metric"><span>Regime Shift</span><strong>${shift.shift_detected?"YES":"NO"}</strong></div><div class="metric"><span>System Health</span><strong>${health.overall}</strong></div><div class="metric"><span>Sharpe / Sortino</span><strong>${fmt(perf.sharpe)} / ${fmt(perf.sortino)}</strong></div><div class="metric"><span>Calmar</span><strong>${fmt(perf.calmar)}</strong></div><div class="metric"><span>Portfolio Heat Items</span><strong>${(heat.heat||[]).length}</strong></div><div class="ai"><b>News:</b> ${news.summary}<br><b>Shift:</b> ${shift.message}<br><b>Performance note:</b> ${perf.note}</div>`;
  }catch(e){$("intelligencePlus").innerHTML="Intelligence Plus trenutno nije dostupan."}
}

async function loadIntelligenceCore(){
  try{
    const s=await api("/api/intelligence/status");
    const mem=(s.memory||[]).slice(0,3).map(m=>`<div class="log"><b>${m.memory_type} · ${m.subject}</b><br>${m.insight}<br><span class="small">confidence ${fmt(m.confidence)} · evidence ${m.evidence_count}</span></div>`).join("");
    const opt=(s.portfolio_optimizer?.selected||[]).map(x=>`<div class="log"><b>${x.signal} · ${x.name}</b><br>Score ${fmt(x.score)} · Committee ${x.committee.decision}</div>`).join("") || "No committee-approved opportunities right now.";
    const mc=s.monte_carlo||{};
    $("intelligenceCore").innerHTML=`<h3>AI Memory</h3>${mem||"No memory yet."}<h3>Portfolio Optimizer</h3>${opt}<h3>Monte Carlo</h3><div class="metric"><span>Ready</span><strong>${mc.ready?"YES":"NO"}</strong></div><div class="metric"><span>Median profit</span><strong>${mc.ready?eur(mc.median_profit):"—"}</strong></div><div class="metric"><span>P90 drawdown</span><strong>${mc.ready?eur(mc.p90_drawdown):"—"}</strong></div><div class="ai">${mc.message||""}</div>`;
  }catch(e){$("intelligenceCore").innerHTML="Intelligence Core trenutno nije dostupan."}
}
async function buildMemory(){await api("/api/intelligence/build-memory",{method:"POST"});$("status").textContent="AI Memory rebuilt";await refresh()}

async function loadControlCenter(){
  try{
    const c=await api("/api/control-center");
    const b=c.best_opportunity;
    $("controlCenter").innerHTML=`<div class="metric"><span>Mode</span><strong>${c.mode.execution_mode}</strong></div><div class="metric"><span>Broker</span><strong>${c.mode.selected_broker}</strong></div><div class="metric"><span>Auto engine</span><strong>${c.mode.auto_engine_enabled?"ON":"OFF"}</strong></div><div class="metric"><span>Live</span><strong>${c.mode.live_enabled?"ON":"LOCKED"}</strong></div><div class="metric"><span>Safety allowed</span><strong>${c.safety.allowed?"YES":"NO"}</strong></div><div class="metric"><span>Daily PnL</span><strong>${eur(c.daily_pnl)}</strong></div><div class="metric"><span>Open positions</span><strong>${(c.open_positions||[]).length}</strong></div><div class="metric"><span>Pending approvals</span><strong>${(c.pending_approvals||[]).length}</strong></div><div class="ai"><b>Best:</b> ${b?`${b.name} ${b.signal} score ${b.ai_score}`:"—"}<br><b>Safety:</b> ${(c.safety.blocked||[]).join("; ")||"clear"}</div>`;
  }catch(e){$("controlCenter").innerHTML="Control Center trenutno nije dostupan."}
}
async function setMode(mode){const r=await api(`/api/control-center/mode/${mode}`,{method:"POST"});$("status").textContent=r.ok?`Mode: ${mode}`:(r.error||"mode error");await refresh()}
async function emergencyStop(){await api("/api/control-center/emergency-stop",{method:"POST"});$("status").textContent="EMERGENCY STOP aktiviran";await refresh()}
async function resumePaper(){await api("/api/control-center/resume-paper",{method:"POST"});$("status").textContent="Paper mode resumed";await refresh()}

async function loadIbkrConnect(){
  try{
    const s=await api("/api/ibkr/status");
    let auth="not connected";
    if(s.auth){
      auth=s.auth.ok?"connected":"not authenticated / gateway offline";
    }
    $("ibkrConnect").innerHTML=`<div class="metric"><span>Base URL</span><strong>${s.base_url}</strong></div><div class="metric"><span>Paper ready</span><strong>${s.paper_ready?"YES":"NO"}</strong></div><div class="metric"><span>Account ID</span><strong>${s.account_id||"not set"}</strong></div><div class="metric"><span>Auth</span><strong>${auth}</strong></div><div class="ai">For IBKR paper execution you need IBKR Client Portal Gateway/TWS running and IBKR_ACCOUNT_ID set.</div>`;
  }catch(e){$("ibkrConnect").innerHTML="IBKR status nije dostupan. Gateway verovatno nije pokrenut."}
}

async function loadBrokerEngineFull(){
  try{
    const b=await api("/api/broker-engine/status");
    $("brokerEngineFull").innerHTML=`<div class="metric"><span>Selected</span><strong>${b.selected}</strong></div><div class="metric"><span>Execution mode</span><strong>${b.execution_mode}</strong></div><div class="metric"><span>Live enabled</span><strong>${b.live_enabled?"YES":"NO / LOCKED"}</strong></div><div class="metric"><span>Confirm required</span><strong>${b.confirm_required?"YES":"NO"}</strong></div><div class="metric"><span>Capital.com</span><strong>${b.adapters.capital_com.configured?"CONFIGURED":"NOT CONFIGURED"}</strong></div><div class="metric"><span>IBKR</span><strong>${b.adapters.ibkr.configured?"CONFIGURED":"PLACEHOLDER"}</strong></div><div class="ai">${b.safety}</div>`;
  }catch(e){$("brokerEngineFull").innerHTML="Broker Engine nije dostupan."}
}

async function loadSafetyCore(){
  try{
    const s=await api("/api/safety/status");
    const blocked=(s.blocked||[]).join("<br>") || "Safety clear.";
    $("safetyCore").innerHTML=`<div class="metric"><span>Allowed</span><strong>${s.allowed?"YES":"NO"}</strong></div><div class="metric"><span>Kill switch</span><strong>${s.kill_switch?"ON":"OFF"}</strong></div><div class="metric"><span>No-trade score</span><strong>${s.no_trade.score}/100</strong></div><div class="metric"><span>Cooldown</span><strong>${s.cooldown.active?"ACTIVE":"OFF"}</strong></div><div class="metric"><span>Capital today</span><strong>${eur(s.capital.used_today)} / ${eur(s.capital.allowed_today)}</strong></div><div class="ai">${blocked}<br>${s.no_trade.reason||""}</div>`;
  }catch(e){$("safetyCore").innerHTML="Safety status nije dostupan."}
}
async function killSwitchOn(){await api("/api/safety/kill-switch/on",{method:"POST"});await refresh()}
async function killSwitchOff(){await api("/api/safety/kill-switch/off",{method:"POST"});await refresh()}

async function loadBrokerApprovalCore(){
  try{
    const b=await api("/api/broker/config");
    $("brokerCore").innerHTML=`<div class="metric"><span>Execution mode</span><strong>${b.execution_mode}</strong></div><div class="metric"><span>Selected broker</span><strong>${b.selected_broker}</strong></div><div class="metric"><span>Auto mode</span><strong>${b.auto_locked?"LOCKED":"OPEN"}</strong></div><div class="metric"><span>Capital.com</span><strong>${b.capital_com_configured?"CONFIGURED":"NOT CONFIGURED"}</strong></div><div class="metric"><span>IBKR</span><strong>${b.ibkr_configured?"CONFIGURED":"PLACEHOLDER"}</strong></div><div class="ai">${b.safety}</div>`;
  }catch(e){$("brokerCore").innerHTML="Broker core nije dostupan."}
  try{
    const p=await api("/api/approvals/pending");
    const rows=p.approvals||[];
    $("pendingApprovals").innerHTML=rows.map(a=>`<div class="log"><b>${a.side} ${a.name}</b><br>Score ${fmt(a.ai_score)} · Qty ${fmt(a.qty,4)} · Entry ${fmt(a.entry)}<br>${a.ai_explanation||""}<br><button onclick="approveTrade(${a.id})">Approve Paper</button><button class="secondary" onclick="rejectTrade(${a.id})">Reject</button></div>`).join("") || "Nema pending approval naloga.";
  }catch(e){$("pendingApprovals").innerHTML="Pending approvals nisu dostupni."}
}
async function approveTrade(id){const r=await api(`/api/broker-engine/execute/${id}?broker=paper`,{method:"POST"});$("status").textContent=r.ok?"Approved / paper executed":(r.error||"Error");await refresh()}
async function rejectTrade(id){const r=await api(`/api/approvals/${id}/reject`,{method:"POST"});$("status").textContent=r.ok?"Rejected":(r.error||"Error");await refresh()}

async function loadAdvancedRisk(){
  try{
    const g=await api("/api/risk/guardrails");
    $("riskGuardrails").innerHTML=`<div class="metric"><span>Allowed</span><strong>${g.allowed?"YES":"NO"}</strong></div><div class="metric"><span>Blocked</span><strong>${(g.blocked||[]).length}</strong></div><div class="metric"><span>Warnings</span><strong>${(g.warnings||[]).length}</strong></div><div class="ai">${[...(g.blocked||[]),...(g.warnings||[])].join("<br>")||"Risk guardrails are clear."}</div>`;
  }catch(e){$("riskGuardrails").innerHTML="Risk guardrails nisu dostupni."}
}
async function runBacktest(){
  const sym=$("backtestSymbol").value||"NVDA";
  const st=$("backtestStrategy").value;
  $("backtestLab").innerHTML="Backtest running...";
  const r=await api(`/api/backtest/${encodeURIComponent(sym)}?strategy=${encodeURIComponent(st)}`);
  if(r.error){$("backtestLab").innerHTML=r.error;return}
  $("backtestLab").innerHTML=`<div class="metric"><span>${r.name}</span><strong>${r.strategy}</strong></div><div class="metric"><span>Trades</span><strong>${r.trades}</strong></div><div class="metric"><span>Win rate</span><strong>${fmt(r.win_rate)}%</strong></div><div class="metric"><span>Profit factor</span><strong>${fmt(r.profit_factor)}</strong></div><div class="metric"><span>Total points</span><strong>${fmt(r.total_points,4)}</strong></div><div class="metric"><span>Max DD points</span><strong>${fmt(r.max_drawdown_points,4)}</strong></div><div class="ai">${r.warning}</div>`;
}
async function runWatchlistBacktest(){
  const st=$("backtestStrategy").value;
  $("backtestLab").innerHTML="Watchlist backtest running...";
  const r=await api(`/api/backtest-watchlist?strategy=${encodeURIComponent(st)}`);
  $("backtestLab").innerHTML=(r.results||[]).map(x=>`<div class="log"><b>${x.symbol} · ${x.name}</b><br>Trades ${x.trades} · Win ${fmt(x.win_rate)}% · PF ${fmt(x.profit_factor)} · Points ${fmt(x.total_points,4)}</div>`).join("")||"Nema rezultata.";
}

async function loadStrategyLab(){
  try{
    const s=await api("/api/strategy-lab/summary");
    const strategies=s.strategies||{};
    const rows=Object.entries(strategies).slice(0,8);
    $("strategyLab").innerHTML=rows.map(([name,d])=>`<div class="log"><b>${name}</b><br>Signals ${d.signals||0} · Paper trades ${d.paper_trades||0} · PnL ${eur(d.pnl||0)}<br>Win rate ${fmt(d.win_rate||0)}% · Profit factor ${fmt(d.profit_factor||0)} · Avg score ${fmt(d.avg_score||0)}</div>`).join("") || "Još nema dovoljno podataka.";
  }catch(e){$("strategyLab").innerHTML="Strategy Lab trenutno nije dostupan."}
}

async function loadAiJournal(){
  try{
    const j=await api("/api/ai/journal");
    const lessons=(j.lessons||[]).map(x=>`<div class="ai">${x}</div>`).join("");
    const decisions=(j.recent_decisions||[]).slice(0,5).map(d=>`<div class="log"><b>${d.decision} · ${d.name}</b><br>${d.strategy} · ${d.regime} · Score ${fmt(d.score)}<br><span class="small">${d.ts}</span></div>`).join("");
    $("aiJournal").innerHTML=lessons+decisions;
  }catch(e){$("aiJournal").innerHTML="AI Journal trenutno nije dostupan."}
}

async function loadProfessionalCore(){
  try{
    const p=await api("/api/portfolio/health");
    $("portfolioHealth").innerHTML=`<div class="metric"><span>Status</span><strong>${p.status}</strong></div><div class="metric"><span>Open positions</span><strong>${p.open_positions}</strong></div><div class="metric"><span>Total risk</span><strong>${eur(p.total_risk_eur)} (${fmt(p.total_risk_pct)}%)</strong></div><div class="ai">${(p.warnings||[]).join("<br>")||"Portfolio risk is within limits."}</div>`;
  }catch(e){$("portfolioHealth").innerHTML="Portfolio Health nije dostupan."}
  try{
    const a=await api("/api/analytics/performance");
    $("performanceAnalytics").innerHTML=`<div class="metric"><span>PnL</span><strong>${eur(a.pnl)}</strong></div><div class="metric"><span>Win rate</span><strong>${fmt(a.win_rate)}%</strong></div><div class="metric"><span>Profit factor</span><strong>${fmt(a.profit_factor)}</strong></div><div class="metric"><span>Expectancy</span><strong>${eur(a.expectancy)}</strong></div><div class="metric"><span>Max drawdown</span><strong>${eur(a.max_drawdown)}</strong></div>`;
  }catch(e){$("performanceAnalytics").innerHTML="Analytics nije dostupan."}
  try{
    const b=await api("/api/broker/status");
    $("brokerStatus").innerHTML=`<div class="metric"><span>Mode</span><strong>${b.mode}</strong></div><div class="metric"><span>Approval mode</span><strong>${b.approval_mode_ready?"READY":"NO"}</strong></div><div class="metric"><span>Auto mode</span><strong>${b.auto_mode_locked?"LOCKED":"OPEN"}</strong></div><div class="ai">${b.safety}</div>`;
  }catch(e){$("brokerStatus").innerHTML="Broker status nije dostupan."}
}

async function refresh(){await settings();await loadMarket();await loadBrief();await loadAudit();await loadPaper();await loadProfessionalCore();await loadIbkrExecution();await loadHybridMode();await loadProfessional50();await loadOilCfdEngine();await loadIntelligencePlus();await loadIntelligenceCore();await loadControlCenter();await loadIbkrConnect();await loadBrokerEngineFull();await loadSafetyCore();await loadBrokerApprovalCore();await loadAdvancedRisk();await loadStrategyLab();await loadAiJournal()}$("refresh").onclick=refresh;$("run").onclick=run;$("reset").onclick=reset;$("save").onclick=save;$("filter").onchange=render;$("dailyReport").onclick=()=>showReport("daily");$("weeklyReport").onclick=()=>showReport("weekly");$("allReport").onclick=()=>showReport("all");$("runBacktest").onclick=runBacktest;$("runWatchlistBacktest").onclick=runWatchlistBacktest;$("killOn").onclick=killSwitchOn;$("killOff").onclick=killSwitchOff;$("checkIbkr").onclick=loadIbkrConnect;$("modePaper").onclick=()=>setMode("paper");$("modeApproval").onclick=()=>setMode("approval");$("emergencyStop").onclick=emergencyStop;$("resumePaper").onclick=resumePaper;$("buildMemory").onclick=buildMemory;$("biasNeutral").onclick=()=>setOilBias("neutral");$("biasOilBull").onclick=()=>setOilBias("oil_bullish");$("biasOilBear").onclick=()=>setOilBias("oil_bearish");refresh();setInterval(refresh,60000);