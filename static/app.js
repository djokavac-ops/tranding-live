const $ = id => document.getElementById(id);
const fmt = (n, d=2) => Number.isFinite(n) ? Number(n).toLocaleString("de-DE",{maximumFractionDigits:d}) : "—";

function cls(signal, trend){
  if(signal.includes("BUY")) return "signal BUY";
  if(signal.includes("SELL")) return "signal SELL";
  if(trend === "BULLISH") return "signal BULLISH";
  if(trend === "BEARISH") return "signal BEARISH";
  return "signal WAIT";
}

async function load(){
  const box = $("cards");
  box.innerHTML = "<p>Učitavam cene...</p>";
  try{
    const res = await fetch("/api/market");
    const data = await res.json();
    box.innerHTML = "";
    Object.entries(data).forEach(([key, x]) => {
      if(x.error){ return; }
      const pos = x.position;
      const div = document.createElement("section");
      div.className = "card";
      div.innerHTML = `
        <div class="top">
          <div>
            <div class="name">${x.name}</div>
            <div class="${cls(x.signal, x.trend)}">${x.signal}</div>
          </div>
          <div class="price">${fmt(x.price, 4)}</div>
        </div>
        <p>${x.reason}</p>
        <div class="metric"><span>Trend</span><strong>${x.trend}</strong></div>
        <div class="metric"><span>RSI</span><strong>${fmt(x.rsi)}</strong></div>
        <div class="metric"><span>EMA20 / EMA50 / EMA200</span><strong>${fmt(x.ema20)} / ${fmt(x.ema50)} / ${fmt(x.ema200)}</strong></div>
        <div class="metric"><span>ATR stop / target long</span><strong>${fmt(x.long_stop)} / ${fmt(x.long_target)}</strong></div>
        ${pos ? `
        <div class="metric"><span>Tvoja pozicija</span><strong>${pos.side} @ ${pos.entry}</strong></div>
        <div class="metric"><span>PnL</span><strong>${fmt(pos.pnl)} €</strong></div>
        <div class="metric"><span>Do stopa / targeta</span><strong>${fmt(pos.to_stop_pct)}% / ${fmt(pos.to_target_pct)}%</strong></div>` : ""}
      `;
      box.appendChild(div);
    });
  }catch(e){
    box.innerHTML = "<p>Greška pri učitavanju. Proveri internet/server.</p>";
  }
}

function riskCalc(){
  const account = parseFloat($("account").value);
  const riskPct = parseFloat($("riskPct").value);
  const entry = parseFloat($("entry").value);
  const stop = parseFloat($("stop").value);
  const riskMoney = account * riskPct / 100;
  const dist = Math.abs(entry-stop);
  $("riskMoney").textContent = fmt(riskMoney) + " €";
  $("qty").textContent = dist > 0 ? fmt(riskMoney / dist, 2) + " units" : "—";
}

["account","riskPct","entry","stop"].forEach(id => $(id).addEventListener("input", riskCalc));
$("refresh").addEventListener("click", load);
$("save").addEventListener("click", () => {
  localStorage.setItem("journal", $("journal").value);
  alert("Sačuvano.");
});
$("journal").value = localStorage.getItem("journal") || "";
riskCalc();
load();
setInterval(load, 60000);
