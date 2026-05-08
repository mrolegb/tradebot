import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CirclePause,
  Power,
  RefreshCcw,
  ShieldAlert,
  TrendingDown,
  TrendingUp
} from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import './styles.css';

const API = '';

function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function money(value) {
  return numberValue(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function percent(value) {
  return `${numberValue(value).toFixed(2)}%`;
}

async function request(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep HTTP status text if the response has no JSON body.
    }
    throw new Error(detail);
  }
  return response.json();
}

function App() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function load() {
    try {
      const dashboard = await request('/api/dashboard');
      setData(dashboard);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  }

  async function action(label, path) {
    setBusy(label);
    try {
      await request(path, { method: 'POST' });
      await load();
      setMessage(`${label} completed`);
      setError('');
    } catch (err) {
      setError(err.message);
      setMessage('');
    } finally {
      setBusy('');
    }
  }

  async function selectRuntime(label, path, value) {
    setBusy(label);
    try {
      await request(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value })
      });
      await load();
      setMessage(`${label} changed`);
      setError('');
    } catch (err) {
      setError(err.message);
      setMessage('');
    } finally {
      setBusy('');
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const reports = data?.reports ?? {};
  const summary = reports.summary ?? {};
  const aggregate = reports.aggregate ?? {};
  const config = data?.config ?? {};
  const runtime = data?.runtime ?? {};
  const options = data?.options ?? {};
  const profiles = options.profiles ?? {};
  const strategies = options.strategies ?? {};
  const equity = useMemo(
    () =>
      (reports.equity ?? []).map((row, index) => ({
        index,
        balance: numberValue(row.balance),
        drawdown: numberValue(row.drawdown_percent)
      })),
    [reports.equity]
  );

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">Local Monitor</p>
          <h1>Tradebot Dashboard</h1>
        </div>
        <div className="status-strip">
          <span className={runtime.running ? 'pill good' : 'pill'}>
            {runtime.running ? 'Running' : 'Stopped'}
          </span>
          <span className="pill">{config.mode ?? 'unknown'}</span>
          <button className="icon-button" onClick={load} title="Refresh dashboard">
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      {error && (
        <section className="notice">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </section>
      )}
      {message && !error && (
        <section className="notice success">
          <Activity size={18} />
          <span>{message}</span>
        </section>
      )}

      <section className="toolbar">
        <label className="select-field">
          <span>Config</span>
          <select
            value={runtime.selected_profile ?? 'simulation'}
            onChange={(event) => selectRuntime('profile', '/api/runtime/profile', event.target.value)}
            disabled={Boolean(busy) || runtime.running}
          >
            {Object.entries(profiles).map(([key, profile]) => (
              <option key={key} value={key}>{profile.label}</option>
            ))}
          </select>
        </label>
        <label className="select-field">
          <span>Strategy</span>
          <select
            value={runtime.selected_strategy ?? 'breakout'}
            onChange={(event) => selectRuntime('strategy', '/api/runtime/strategy', event.target.value)}
            disabled={Boolean(busy) || runtime.running}
          >
            {Object.entries(strategies).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </label>
        <button onClick={() => action('start', '/api/control/start')} disabled={Boolean(busy) || runtime.running}>
          <Power size={17} />
          Start
        </button>
        <button onClick={() => action('stop', '/api/control/stop')} disabled={Boolean(busy) || !runtime.running}>
          <CirclePause size={17} />
          Stop
        </button>
        <button onClick={() => action('report', '/api/simulation/report')} disabled={Boolean(busy) || runtime.running}>
          <BarChart3 size={17} />
          Run Report
        </button>
        <button onClick={() => action('batch', '/api/simulation/batch')} disabled={Boolean(busy) || runtime.running}>
          <Activity size={17} />
          Run Batch
        </button>
        {busy && <span className="busy">Running {busy}...</span>}
      </section>

      <section className="metrics-grid">
        <Metric icon={<TrendingUp />} label="Return" value={percent(summary.return_percent)} tone={numberValue(summary.return_percent) >= 0 ? 'good' : 'bad'} />
        <Metric icon={<Activity />} label="Loop Runs" value={runtime.loop_count ?? 0} tone={runtime.running ? 'good' : 'neutral'} />
        <Metric icon={<BarChart3 />} label="Trades" value={summary.total_trades ?? 0} />
        <Metric icon={<ShieldAlert />} label="Max Drawdown" value={percent(summary.max_drawdown_percent)} tone={numberValue(summary.max_drawdown_percent) < -3 ? 'bad' : 'neutral'} />
        <Metric icon={<TrendingDown />} label="Batch Worst Run" value={percent(aggregate.overall?.worst_return_percent)} tone="bad" />
      </section>

      <section className="layout">
        <Panel title="Equity Curve">
          <div className="chart-box">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={equity}>
                <CartesianGrid stroke="#e6e1d8" vertical={false} />
                <XAxis dataKey="index" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                <Tooltip />
                <Line type="monotone" dataKey="balance" stroke="#216e5b" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Config">
          <dl className="definition-list">
            <dt>Strategy</dt>
            <dd>{strategies[runtime.selected_strategy] ?? config.strategy}</dd>
            <dt>Profile</dt>
            <dd>{profiles[runtime.selected_profile]?.label ?? runtime.selected_profile}</dd>
            <dt>Timeframe</dt>
            <dd>{config.timeframe}</dd>
            <dt>Symbols</dt>
            <dd>{(config.symbols ?? []).join(', ')}</dd>
            <dt>Last Action</dt>
            <dd>{runtime.last_action}</dd>
            <dt>Loop Runs</dt>
            <dd>{runtime.loop_count ?? 0}</dd>
            <dt>Last Run</dt>
            <dd>{runtime.last_run_at ? String(runtime.last_run_at).slice(11, 19) : '-'}</dd>
            <dt>Action Time</dt>
            <dd>{runtime.last_action_at ? String(runtime.last_action_at).slice(11, 19) : '-'}</dd>
          </dl>
        </Panel>
      </section>

      <section className="layout">
        <Panel title="Batch By Regime">
          <RegimeTable regimes={aggregate.by_regime ?? {}} />
        </Panel>
        <Panel title="Latest Trades">
          <TradesTable trades={reports.trades ?? []} />
        </Panel>
      </section>

      <section>
        <Panel title="Latest Signals">
          <SignalsTable signals={reports.signals ?? []} />
        </Panel>
      </section>
    </main>
  );
}

function Metric({ icon, label, value, tone = 'neutral' }) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{React.cloneElement(icon, { size: 20 })}</div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function Panel({ title, children }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function RegimeTable({ regimes }) {
  const rows = Object.entries(regimes);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Regime</th>
            <th>Mean</th>
            <th>Worst</th>
            <th>Positive</th>
            <th>Trades</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, row]) => (
            <tr key={name}>
              <td>{name}</td>
              <td className={numberValue(row.mean_return_percent) >= 0 ? 'text-good' : 'text-bad'}>{percent(row.mean_return_percent)}</td>
              <td>{percent(row.worst_return_percent)}</td>
              <td>{row.positive_runs}/{row.runs}</td>
              <td>{numberValue(row.mean_trades).toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradesTable({ trades }) {
  const rows = trades.slice(-12).reverse();
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Side</th>
            <th>Exit</th>
            <th>PnL</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.entry_time}-${index}`}>
              <td>{row.symbol}</td>
              <td>{row.side}</td>
              <td>{row.exit_reason}</td>
              <td className={numberValue(row.net_pnl) >= 0 ? 'text-good' : 'text-bad'}>{money(row.net_pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SignalsTable({ signals }) {
  const rows = signals.slice(-16).reverse();
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.time}-${row.symbol}-${index}`}>
              <td>{String(row.time).slice(5, 16)}</td>
              <td>{row.symbol}</td>
              <td>{row.side}</td>
              <td>{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
