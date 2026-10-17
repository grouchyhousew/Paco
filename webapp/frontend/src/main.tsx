import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { api } from './api';

type GameId = 'crash' | 'fruit-fall';
type GameResult = { result?: { payout_multiplier?: number; crash_multiplier?: number; cascades?: Array<{ grid_after: string[][] }> }; server_seed?: string; commit?: string };

const games: Array<{ id: GameId; icon: string; title: string; copy: string }> = [
  { id: 'crash', icon: '🚀', title: 'Crash', copy: 'Поймай множитель до взрыва.' },
  { id: 'fruit-fall', icon: '🍉', title: 'Fruit Fall', copy: 'Фрукты падают, комбинации растут.' },
];

function App() {
  const [selected, setSelected] = useState<GameId>('fruit-fall');
  const [balance, setBalance] = useState<number | null>(null);
  const [amount, setAmount] = useState(1);
  const [autoCashout, setAutoCashout] = useState(2);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<GameResult | null>(null);
  const active = useMemo(() => games.find((game) => game.id === selected)!, [selected]);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
    Promise.all([api.me(), api.wallet()])
      .then(([, wallet]) => setBalance(wallet.balance))
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  async function play() {
    setError('');
    setResult(null);
    setPlaying(true);
    const payload = { idempotency_key: `${Date.now()}-${crypto.randomUUID()}`, client_seed: 'telegram-mini-app', nonce: Date.now(), amount };
    try {
      const response = selected === 'fruit-fall'
        ? await api.playFruit({ ...payload, rows: 6, cols: 5 })
        : await api.playCrash({ ...payload, auto_cashout: autoCashout });
      setResult(response);
      const wallet = await api.wallet();
      setBalance(wallet.balance);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Игра недоступна');
    } finally {
      setPlaying(false);
    }
  }

  const displayedGrid = result?.result?.cascades?.at(-1)?.grid_after;
  return <main className="shell">
    <header className="topbar"><div className="mark"><span className="mark-dot" />Savana<span>Win</span></div><div className="balance">{loading ? '…' : `$${(balance ?? 0).toFixed(2)}`} <button aria-label="Пополнить баланс">+</button></div></header>
    <section className="hero"><p className="eyebrow">Твой игровой оазис</p><h1>Играй красиво.<br /><em>Выигрывай честно.</em></h1><p className="sub">Авторитетные раунды, прозрачная математика и серверные результаты.</p><div className="hero-actions"><button className="primary" onClick={() => setError('Пополнение подключается через Crypto Pay после настройки токена.')}>Пополнить баланс</button><button className="ghost" onClick={() => setError('Результат раунда формируется сервером и сохраняется с commit/seed.')}>Правила и честность</button></div></section>
    {error && <div className="notice error" role="alert">{error}</div>}
    <section className="game-grid">{games.map((game) => <button key={game.id} className={`game-card ${selected === game.id ? 'active' : ''}`} onClick={() => { setSelected(game.id); setResult(null); }}><span className="game-icon">{game.icon}</span><span><strong>{game.title}</strong><small>{game.copy}</small></span><span className="arrow">↗</span></button>)}</section>
    <section className="stage"><div className="stage-head"><div><p className="eyebrow">Сейчас выбрано</p><h2>{active.title}</h2></div><span className="live"><i /> {result ? 'ROUND READY' : 'BETA'}</span></div><div className={`visual ${selected}`}><div className="glow" />{selected === 'crash' ? <><div className="multiplier">{result?.result?.crash_multiplier?.toFixed(2) ?? '1.00'}<span>x</span></div><div className="orbit">✦</div><div className="trajectory" /></> : <div className="fruits">{(displayedGrid ?? [['🍋', '🍒', '🍉'], ['🔔', '💎', '🥝'], ['🍇', '🍉', '🍒']]).map((row, index) => <div key={index}>{row.map((fruit, column) => <span key={`${index}-${column}`}>{fruit}</span>)}</div>)}</div>}</div><div className="controls"><div><label htmlFor="amount">Ставка</label><input id="amount" type="number" min="0.1" max="1000" step="0.1" value={amount} onChange={(event) => setAmount(Number(event.target.value))} /></div>{selected === 'crash' && <div><label htmlFor="cashout">Auto cashout</label><input id="cashout" type="number" min="1.01" max="1000" step="0.01" value={autoCashout} onChange={(event) => setAutoCashout(Number(event.target.value))} /></div>}<button className="play" disabled={playing || loading} onClick={play}>{playing ? 'Обработка…' : selected === 'crash' ? 'Войти в раунд' : 'Крутить'}</button></div>{result && <div className="notice success">Результат сервера: {result.result?.payout_multiplier?.toFixed(2) ?? '0.00'}x</div>}</section>
    <nav className="nav"><button className="selected" aria-label="Главная">⌂<small>Главная</small></button><button aria-label="Игры">◈<small>Игры</small></button><button aria-label="Кошелёк">◌<small>Кошелёк</small></button><button aria-label="Профиль">◎<small>Профиль</small></button></nav>
  </main>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
