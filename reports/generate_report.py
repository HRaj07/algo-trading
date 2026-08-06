"""
Report Generator
Generates the GitHub Pages HTML dashboard with live portfolio stats,
recent signals, trade history, and backtest performance charts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# HTML template for the dashboard
DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AlgoTrade India | Live Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg: #0a0e1a;
      --surface: #111827;
      --surface2: #1a2232;
      --border: #1e2d40;
      --accent: #00d4ff;
      --accent2: #7c3aed;
      --green: #10b981;
      --red: #ef4444;
      --amber: #f59e0b;
      --text: #e2e8f0;
      --text-muted: #64748b;
      --text-dim: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.6;
    }}

    /* Header */
    header {{
      background: linear-gradient(135deg, #0f1729 0%, #1a0f2e 50%, #0f1729 100%);
      border-bottom: 1px solid var(--border);
      padding: 0 2rem;
      position: sticky;
      top: 0;
      z-index: 100;
      backdrop-filter: blur(10px);
    }}
    .header-inner {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      max-width: 1400px;
      margin: 0 auto;
      height: 64px;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.5px;
    }}
    .logo-icon {{
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.1rem;
    }}
    .status-badge {{
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: var(--green);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; }}
      50% {{ opacity: 0.3; }}
    }}

    /* Layout */
    .container {{ max-width: 1400px; margin: 0 auto; padding: 2rem; }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }}
    .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
    .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
    @media (max-width: 1024px) {{
      .grid-4 {{ grid-template-columns: repeat(2, 1fr); }}
      .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
    }}

    /* Cards */
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 1.5rem;
      transition: border-color 0.2s, transform 0.2s;
    }}
    .card:hover {{ border-color: rgba(0, 212, 255, 0.3); transform: translateY(-2px); }}
    .card-title {{
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 0.75rem;
    }}
    .metric-value {{
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -1px;
      line-height: 1;
    }}
    .metric-sub {{ font-size: 0.85rem; color: var(--text-muted); margin-top: 0.4rem; }}
    .positive {{ color: var(--green); }}
    .negative {{ color: var(--red); }}
    .neutral {{ color: var(--accent); }}

    /* Section headers */
    .section-title {{
      font-size: 1.1rem;
      font-weight: 700;
      margin-bottom: 1rem;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    /* Signals table */
    .signals-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }}
    .signals-table th {{
      text-align: left;
      padding: 0.75rem 1rem;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }}
    .signals-table td {{
      padding: 0.85rem 1rem;
      border-bottom: 1px solid rgba(30,45,64,0.5);
      color: var(--text-dim);
    }}
    .signals-table tr:hover td {{ background: rgba(0,212,255,0.04); color: var(--text); }}
    .badge {{
      display: inline-block;
      padding: 2px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .badge-buy {{ background: rgba(16,185,129,0.15); color: var(--green); border: 1px solid rgba(16,185,129,0.3); }}
    .badge-sell {{ background: rgba(239,68,68,0.15); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }}
    .badge-hold {{ background: rgba(0,212,255,0.1); color: var(--accent); border: 1px solid rgba(0,212,255,0.2); }}
    .badge-cash {{ background: rgba(245,158,11,0.15); color: var(--amber); border: 1px solid rgba(245,158,11,0.3); }}

    /* Strategy cards */
    .strategy-card {{ background: var(--surface2); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
    .strategy-name {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 0.5rem; }}
    .strategy-stats {{ display: flex; gap: 1.5rem; flex-wrap: wrap; }}
    .stat-item {{ display: flex; flex-direction: column; gap: 2px; }}
    .stat-label {{ font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; }}
    .stat-value {{ font-size: 0.95rem; font-weight: 700; }}

    /* Chart container */
    .chart-wrap {{ position: relative; height: 300px; }}

    /* Footer */
    footer {{
      border-top: 1px solid var(--border);
      padding: 1.5rem 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.8rem;
      margin-top: 2rem;
    }}
    footer a {{ color: var(--accent); text-decoration: none; }}

    /* Disclaimer */
    .disclaimer {{
      background: rgba(245,158,11,0.08);
      border: 1px solid rgba(245,158,11,0.2);
      border-radius: 12px;
      padding: 1rem 1.5rem;
      font-size: 0.82rem;
      color: var(--amber);
      margin-bottom: 1.5rem;
    }}

    /* Gradient border cards */
    .card-gradient {{
      background: linear-gradient(var(--surface), var(--surface)) padding-box,
                  linear-gradient(135deg, var(--accent), var(--accent2)) border-box;
      border: 1px solid transparent;
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="logo">
        <div class="logo-icon">📈</div>
        <span>AlgoTrade <span style="color:var(--accent)">India</span></span>
      </div>
      <div class="status-badge">
        <div class="status-dot"></div>
        Paper Trading Active
      </div>
      <div style="font-size:0.8rem; color:var(--text-muted)">
        Last updated: {last_updated}
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Disclaimer -->
    <div class="disclaimer">
      ⚠️ <strong>Paper Trading Mode</strong> — This system generates signals for educational purposes only.
      Past performance does not guarantee future results. Not financial advice.
    </div>

    <!-- KPI Row -->
    <div class="grid-4">
      <div class="card card-gradient">
        <div class="card-title">Portfolio Value</div>
        <div class="metric-value neutral">₹{portfolio_value}</div>
        <div class="metric-sub">Initial: ₹{initial_capital}</div>
      </div>
      <div class="card">
        <div class="card-title">Total Return</div>
        <div class="metric-value {return_class}">{total_return}%</div>
        <div class="metric-sub">Since inception</div>
      </div>
      <div class="card">
        <div class="card-title">Active Positions</div>
        <div class="metric-value neutral">{n_positions}</div>
        <div class="metric-sub">{position_list}</div>
      </div>
      <div class="card">
        <div class="card-title">Today's Signals</div>
        <div class="metric-value neutral">{n_signals}</div>
        <div class="metric-sub">{signal_date}</div>
      </div>
    </div>

    <!-- Strategy Performance -->
    <div class="section-title">📊 Strategy Performance (Backtest)</div>
    <div class="grid-3">
      {strategy_cards}
    </div>

    <!-- Charts & Signals -->
    <div class="grid-2">
      <div class="card">
        <div class="section-title">📈 Portfolio Growth</div>
        <div class="chart-wrap">
          <canvas id="portfolioChart"></canvas>
        </div>
      </div>
      <div class="card">
        <div class="section-title">🎯 Today's Signals</div>
        <table class="signals-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Signal</th>
              <th>Strategy</th>
              <th>Price</th>
              <th>Stop Loss</th>
            </tr>
          </thead>
          <tbody>
            {signals_rows}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent Trades -->
    <div class="card">
      <div class="section-title">📋 Recent Trades</div>
      <table class="signals-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Action</th>
            <th>Ticker</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Value</th>
            <th>PnL</th>
            <th>Strategy</th>
          </tr>
        </thead>
        <tbody>
          {trades_rows}
        </tbody>
      </table>
    </div>
  </div>

  <footer>
    AlgoTrade India | GitHub Actions Powered | 
    <a href="https://github.com" target="_blank">View Repository</a> |
    Data from Yahoo Finance (yfinance)
  </footer>

  <script>
    // Portfolio Growth Chart
    const ctx = document.getElementById('portfolioChart').getContext('2d');
    const chartData = {portfolio_chart_data};
    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: chartData.dates,
        datasets: [{{
          label: 'Portfolio Value',
          data: chartData.values,
          borderColor: '#00d4ff',
          backgroundColor: 'rgba(0,212,255,0.08)',
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2,
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }}}},
        scales: {{
          x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#64748b', maxTicksLimit: 6 }} }},
          y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ color: '#64748b', callback: v => '₹' + (v/100000).toFixed(1) + 'L' }} }}
        }}
      }}
    }});
  </script>
</body>
</html>"""


class ReportGenerator:
    """Generates HTML dashboard reports."""

    def __init__(
        self,
        log_dir: str = "logs",
        backtest_dir: str = "backtest_results",
        report_dir: str = "reports",
    ):
        self.log_dir = Path(log_dir)
        self.backtest_dir = Path(backtest_dir)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: str) -> Dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_csv_signals(self) -> List[Dict]:
        signals_path = self.log_dir / "signals.json"
        try:
            with open(signals_path) as f:
                lines = f.readlines()
            if lines:
                return json.loads(lines[-1].strip())  # Latest signals
        except Exception:
            pass
        return []

    def _make_strategy_cards(self, backtest_data: List[Dict]) -> str:
        cards = []
        for b in backtest_data:
            cagr = b.get("cagr_pct", 0)
            sharpe = b.get("sharpe_ratio", 0)
            max_dd = b.get("max_drawdown_pct", 0)
            cagr_class = "positive" if cagr > 12 else "negative" if cagr < 0 else "neutral"
            cards.append(f"""
            <div class="strategy-card">
              <div class="strategy-name">{b.get('strategy', 'N/A')}</div>
              <div class="strategy-stats">
                <div class="stat-item">
                  <span class="stat-label">CAGR</span>
                  <span class="stat-value {cagr_class}">{cagr}%</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Sharpe</span>
                  <span class="stat-value">{sharpe}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Max DD</span>
                  <span class="stat-value negative">{max_dd}%</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Alpha</span>
                  <span class="stat-value positive">{b.get('alpha_pct', 'N/A')}%</span>
                </div>
              </div>
            </div>""")
        return "\n".join(cards) if cards else "<div class='strategy-card'>No backtest data yet. Run the backtest workflow.</div>"

    def _make_signal_rows(self, signals: List[Dict]) -> str:
        if not signals:
            return "<tr><td colspan='5' style='color:var(--text-muted);text-align:center'>No signals today</td></tr>"
        rows = []
        for s in signals:
            badge_class = f"badge-{'buy' if s.get('signal') == 'BUY' else 'sell' if s.get('signal') == 'SELL' else 'hold'}"
            rows.append(f"""
            <tr>
              <td><strong>{s.get('ticker', '-')}</strong></td>
              <td><span class="badge {badge_class}">{s.get('signal', '-')}</span></td>
              <td><span style="color:var(--text-muted)">{s.get('signal_type', '-')}</span></td>
              <td>₹{s.get('current_price', '-')}</td>
              <td>₹{s.get('stop_loss', '-')}</td>
            </tr>""")
        return "\n".join(rows)

    def _make_trade_rows(self, trades: List[Dict]) -> str:
        if not trades:
            return "<tr><td colspan='8' style='color:var(--text-muted);text-align:center'>No trades yet</td></tr>"
        rows = []
        for t in reversed(trades[-20:]):  # Last 20 trades
            pnl = t.get("pnl", None)
            pnl_str = f"<span class='{'positive' if pnl and pnl > 0 else 'negative'}'>₹{pnl:,.0f}</span>" if pnl else "-"
            rows.append(f"""
            <tr>
              <td>{t.get('date', '-')[:10]}</td>
              <td><span class="badge badge-{'buy' if t.get('action') == 'BUY' else 'sell'}">{t.get('action', '-')}</span></td>
              <td><strong>{t.get('ticker', '-')}</strong></td>
              <td>{t.get('qty', '-')}</td>
              <td>₹{t.get('price', 0):,.2f}</td>
              <td>₹{t.get('value', 0):,.0f}</td>
              <td>{pnl_str}</td>
              <td><span style="color:var(--text-muted)">{t.get('strategy', '-')}</span></td>
            </tr>""")
        return "\n".join(rows)

    def generate(
        self,
        today_signals: List[Dict] = None,
        portfolio_summary: Dict = None,
        backtest_results: List[Dict] = None,
        portfolio_history: List[float] = None,
        history_dates: List[str] = None,
    ) -> str:
        """Generate the full HTML dashboard."""
        perf = self._load_json("logs/performance.json")
        portfolio = portfolio_summary or {}
        signals = today_signals or self._load_csv_signals()
        backtests = backtest_results or []

        # Load backtest JSONs if not provided
        if not backtests:
            for strat in ["dual_momentum", "momentum_breakout", "mean_reversion"]:
                bpath = self.backtest_dir / f"{strat}_results.json"
                if bpath.exists():
                    backtests.append(self._load_json(bpath))

        # Load trade history
        state_path = self.log_dir / "portfolio_state.json"
        state = self._load_json(state_path) if state_path.exists() else {}
        trades = state.get("trade_history", [])

        # Format portfolio value
        pv = perf.get("portfolio_value", portfolio.get("total_value", 1_000_000))
        initial = perf.get("initial_capital", 1_000_000)
        total_ret = perf.get("total_return_pct", 0)
        return_class = "positive" if total_ret >= 0 else "negative"

        # Chart data
        chart_data = json.dumps({
            "dates": history_dates or [],
            "values": portfolio_history or [],
        })

        html = DASHBOARD_TEMPLATE.format(
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M IST"),
            portfolio_value=f"{pv:,.0f}",
            initial_capital=f"{initial:,.0f}",
            total_return=f"{total_ret:+.2f}",
            return_class=return_class,
            n_positions=portfolio.get("n_positions", len(state.get("positions", {}))),
            position_list=", ".join(list(state.get("positions", {}).keys())[:3]) or "None",
            n_signals=len([s for s in signals if s.get("signal") == "BUY"]),
            signal_date=datetime.now().strftime("%d %b %Y"),
            strategy_cards=self._make_strategy_cards(backtests),
            signals_rows=self._make_signal_rows([s for s in signals if s.get("signal") == "BUY"]),
            trades_rows=self._make_trade_rows(trades),
            portfolio_chart_data=chart_data,
        )

        output_path = self.report_dir / "index.html"
        with open(output_path, "w") as f:
            f.write(html)

        logger.info(f"Dashboard generated: {output_path}")
        return str(output_path)
