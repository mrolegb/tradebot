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
  const supervisor = data?.supervisor ?? {};
  const operations = data?.operations ?? [];
  const engine = data?.engine ?? {};
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
          <span className={supervisor.active ? 'pill good' : 'pill'}>
            {supervisor.active ? 'Supervisor Active' : 'Supervisor Idle'}
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
        <button onClick={() => action('supervisor', '/api/runtime/supervisor/start')} disabled={Boolean(busy)}>
          <ShieldAlert size={17} />
          Start Supervisor
        </button>
        <button onClick={() => action('pause', '/api/control/pause')} disabled={Boolean(busy)}>
          <CirclePause size={17} />
          Pause
        </button>
        {busy && <span className="busy">Running {busy}...</span>}
      </section>

      <section className="metrics-grid">
        <Metric icon={<TrendingUp />} label="Return" value={percent(summary.return_percent)} tone={numberValue(summary.return_percent) >= 0 ? 'good' : 'bad'} />
        <Metric icon={<Activity />} label="Loop Runs" value={runtime.loop_count ?? 0} tone={runtime.running ? 'good' : 'neutral'} />
        <Metric icon={<BarChart3 />} label="Trades" value={summary.total_trades ?? 0} />
        <Metric icon={<ShieldAlert />} label="Watchdog Errors" value={supervisor.snapshot?.watchdog?.consecutive_errors ?? 0} tone={(supervisor.snapshot?.watchdog?.consecutive_errors ?? 0) > 0 ? 'bad' : 'good'} />
        <Metric icon={<TrendingDown />} label="Batch Worst Run" value={percent(aggregate.overall?.worst_return_percent)} tone="bad" />
      </section>

      <section className="layout">
        <Panel title="Supervisor Status">
          <dl className="definition-list">
            <dt>Active</dt>
            <dd>{String(supervisor.active ?? false)}</dd>
            <dt>Task Running</dt>
            <dd>{String(supervisor.task_running ?? false)}</dd>
            <dt>State</dt>
            <dd>{supervisor.snapshot?.state ?? '-'}</dd>
            <dt>Heartbeat</dt>
            <dd>{supervisor.snapshot?.watchdog?.heartbeat_at ?? '-'}</dd>
            <dt>Last Cycle</dt>
            <dd>{supervisor.snapshot?.watchdog?.last_cycle_at ?? '-'}</dd>
            <dt>Last Error</dt>
            <dd>{supervisor.snapshot?.watchdog?.last_error ?? '-'}</dd>
          </dl>
        </Panel>

        <Panel title="Engine Cycle">
          <dl className="definition-list">
            <dt>Mode</dt>
            <dd>{engine?.mode ?? '-'}</dd>
            <dt>Intent</dt>
            <dd>{engine?.intent?.intent ?? '-'}</dd>
            <dt>Reason</dt>
            <dd>{engine?.intent?.reason ?? '-'}</dd>
            <dt>Executed</dt>
            <dd>{String(engine?.execution?.executed ?? false)}</dd>
            <dt>Safety</dt>
            <dd>{engine?.safety?.reason ?? '-'}</dd>
            <dt>Reconciliation</dt>
            <dd>{String(engine?.reconciliation?.healthy ?? false)}</dd>
          </dl>
        </Panel>
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

        <Panel title="Runtime Operations">
          <OperationsTable rows={operations} />
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

function OperationsTable({ rows }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Action</th>
            <th>Status</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 12).map((row, index) => (
            <tr key={`${row.id}-${index}`}>
              <td>{row.symbol}</td>
              <td>{row.action}</td>
              <td>{row.status}</td>
              <td>{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
