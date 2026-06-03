"use client";

import React, { useState, useEffect } from 'react';
import { Activity, Shield, Cpu, Clock, TerminalSquare, X } from "lucide-react";

// Helper to generate simulated volatility charts when live ticks are not streamed
const generateData = (start: number, volatility: number) => {
  let val = start;
  return Array.from({ length: 40 }).map(() => {
    val = val + (Math.random() - 0.5) * volatility;
    return { value: val };
  });
};

const COIN_CONFIGS: Record<string, { price: number, vol: number, minQty: number, precision: number, minNotional: number }> = {
  'BTC/USDT': { price: 92400, vol: 200, minQty: 0.00001, precision: 5, minNotional: 5.0 },
  'ETH/USDT': { price: 3120, vol: 15, minQty: 0.0001, precision: 4, minNotional: 5.0 },
};

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [selectedCoin, setSelectedCoin] = useState<string | null>(null);
  
  const [systemState, setSystemState] = useState({
    wallet: 100.0,
    timestamp: "",
    risk: {
      loss_today: 0.0,
      consecutive_losses: 0,
      trades_today: 0,
      wins_today: 0,
      losses_today: 0,
      win_rate: 0.0,
      daily_pnl_pct: 0.0,
      cooldown_until: null as string | null
    },
    heartbeats: {} as Record<string, string>,
    prices: {} as Record<string, number>
  });
  
  const [activeTrades, setActiveTrades] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [backendOnline, setBackendOnline] = useState(false);
  
  // Sparkline state caches to keep line drawing stable
  const [sparklines] = useState(() => ({
    'BTC/USDT': generateData(92400, 200),
    'ETH/USDT': generateData(3120, 15)
  }));

  useEffect(() => {
    setMounted(true);
    
    const fetchAllData = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || 
          (typeof window !== 'undefined' 
            ? (window.location.port === '3000' 
                ? `${window.location.protocol}//${window.location.hostname}:8000` 
                : '') 
            : 'http://127.0.0.1:8000');

        const [stateRes, tradesRes, historyRes, logsRes] = await Promise.all([
          fetch(`${apiBase}/api/state`),
          fetch(`${apiBase}/api/trades`),
          fetch(`${apiBase}/api/history`),
          fetch(`${apiBase}/api/logs`)
        ]);
        
        if (stateRes.ok && tradesRes.ok && historyRes.ok && logsRes.ok) {
          const stateData = await stateRes.json();
          const tradesData = await tradesRes.json();
          const historyData = await historyRes.json();
          const logsData = await logsRes.json();
          
          setSystemState(stateData);
          setActiveTrades(tradesData);
          setHistory(historyData);
          setLogs(logsData);
          setBackendOnline(true);
        } else {
          setBackendOnline(false);
        }
      } catch (err) {
        setBackendOnline(false);
      }
    };
    
    fetchAllData();
    const interval = setInterval(fetchAllData, 2000);
    return () => clearInterval(interval);
  }, []);

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-300 font-mono p-4 selection:bg-zinc-800">
      <div className="max-w-[1800px] mx-auto space-y-4 text-xs">
        
        {/* HEADER */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-800/60">
          <div className="flex items-center gap-3">
            <TerminalSquare size={16} className="text-zinc-500" />
            <h1 className="text-sm tracking-widest text-zinc-100 uppercase">Quant Terminal // Node-01</h1>
            <span className={`px-2 py-0.5 border uppercase tracking-widest text-[10px] ${backendOnline ? 'border-zinc-700 bg-zinc-900/50 text-zinc-400' : 'border-zinc-800 bg-zinc-950 text-zinc-600'}`}>
              {backendOnline ? 'Live Feed Connected' : 'Local Sandbox Mode'}
            </span>
          </div>

          <div className="flex items-center gap-4 text-zinc-500">
            <span className="flex items-center gap-2">
              <Clock size={12} /> {new Date().toISOString().split('T')[1].split('.')[0]} UTC
            </span>
            <span className="flex items-center gap-2">
              <Activity size={12} /> LATENCY: {backendOnline ? '4ms' : '0ms'}
            </span>
            <span className="flex items-center gap-2">
              <Cpu size={12} /> CPU: {backendOnline ? '8%' : '1%'}
            </span>
          </div>
        </header>

        {/* METRICS ROW */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Metric 
            title="TOTAL CAPITAL" 
            value={`$${systemState.wallet.toFixed(2)}`} 
            sub={`${systemState.risk.daily_pnl_pct.toFixed(2)}% TODAY`} 
          />
          <Metric 
            title="BOT WIN RATE" 
            value={`${systemState.risk.win_rate.toFixed(1)}%`} 
            sub={`${systemState.risk.trades_today} CYCLES TODAY`} 
          />
          <Metric 
            title="DAILY NET PNL" 
            value={`${systemState.risk.loss_today >= 0 ? '+' : ''}$${systemState.risk.loss_today.toFixed(2)}`} 
            sub={`${systemState.risk.wins_today} W - ${systemState.risk.losses_today} L`} 
          />
          <Metric 
            title="RISK CONTROL" 
            value={systemState.risk.cooldown_until ? "COOLDOWN" : "MONITORING"} 
            sub={systemState.risk.cooldown_until ? `ACTIVE UNTIL ${systemState.risk.cooldown_until.split('T')[1]?.slice(0, 5) || ''}` : "STABLE REGIME"} 
          />
        </div>

        {/* COIN SCANNERS */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.keys(COIN_CONFIGS).map((symbol) => {
            const isSelected = selectedCoin === symbol;
            const lastScan = systemState.heartbeats[symbol] || "STANDBY";
            const livePrice = systemState.prices?.[symbol] || COIN_CONFIGS[symbol].price;
            return (
              <div 
                key={symbol} 
                onClick={() => setSelectedCoin(isSelected ? null : symbol)}
                className={`bg-[#111111] border p-4 relative flex flex-col h-32 hover:border-zinc-600 transition-all cursor-pointer ${isSelected ? 'border-zinc-400 ring-1 ring-zinc-500/20' : 'border-zinc-800/80'}`}
              >
                <div className="flex justify-between items-center mb-2 z-10">
                  <span className="text-zinc-100 font-medium tracking-wide">{symbol}</span>
                  <span className="text-[10px] text-zinc-500 flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 rounded-full ${lastScan !== "STANDBY" ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-zinc-700'}`}></span>
                    {lastScan !== "STANDBY" ? `SCAN: ${lastScan}` : 'STANDBY'}
                  </span>
                </div>
                <div className="mt-auto flex justify-between items-end z-10">
                  <div>
                    <span className="text-zinc-500 text-[10px] block font-mono">LIVE VALUE</span>
                    <span className="text-base text-zinc-100 font-semibold font-mono">
                      ${livePrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-zinc-500 text-[10px] block font-mono">ATR_VOL</span>
                    <span className="text-[10px] text-zinc-400 font-mono">
                      ±${COIN_CONFIGS[symbol].vol}
                    </span>
                  </div>
                </div>
                <div className="absolute bottom-0 left-0 right-0 h-16 opacity-10 pointer-events-none px-2">
                  <Sparkline data={sparklines[symbol as keyof typeof sparklines]} />
                </div>
              </div>
            );
          })}
        </div>

        {/* DETAILS PANEL (DYNAMIC DRAWER IF SELECTED) */}
        {selectedCoin && (
          <div className="bg-[#111111] border border-zinc-500/30 p-4 relative transition-all duration-300">
            <button 
              onClick={() => setSelectedCoin(null)} 
              className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <X size={16} />
            </button>
            <div className="flex items-center gap-2 mb-4 pb-2 border-b border-zinc-800/60">
              <span className="text-zinc-100 font-bold uppercase tracking-wider">{selectedCoin} PARAMETERS & SIGNAL CONFLUENCE</span>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <span className="text-zinc-500 block mb-1">Exchange Rules</span>
                <span className="text-zinc-300 block">Min Quantity: {COIN_CONFIGS[selectedCoin].minQty}</span>
                <span className="text-zinc-300 block">Qty Precision: {COIN_CONFIGS[selectedCoin].precision}</span>
                <span className="text-zinc-300 block">Min Notional: ${COIN_CONFIGS[selectedCoin].minNotional.toFixed(2)}</span>
              </div>
              
              <div>
                <span className="text-zinc-500 block mb-1">Live Status Indicators</span>
                <span className="text-zinc-300 block">Regime Mode: Adaptive Confluence</span>
                <span className="text-zinc-300 block">Signal Interval: 5m / 1h trend</span>
                <span className="text-zinc-300 block">Status: {systemState.heartbeats[selectedCoin] ? 'Active Monitoring' : 'Idle Queue'}</span>
              </div>

              <div>
                <span className="text-zinc-500 block mb-1">Technical Verdict</span>
                <span className="text-zinc-300 block">Momentum Juror: Waiting Scan</span>
                <span className="text-zinc-300 block">RSI Divergence: None</span>
                <span className="text-zinc-300 block">Model Verdict: STANDBY</span>
              </div>

              <div>
                <span className="text-zinc-500 block mb-1">Risk Bounds</span>
                <span className="text-zinc-300 block">ATR Scale: 14 bar rolling</span>
                <span className="text-zinc-300 block">Order Cap: 25% of Wallet</span>
                <span className="text-zinc-300 block">Max Lever: 1x Spot</span>
              </div>
            </div>
          </div>
        )}

        {/* LOWER SECTION */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          
          {/* POSITIONS */}
          <div className="lg:col-span-2 bg-[#111111] border border-zinc-800/80 p-4 min-h-[300px] flex flex-col">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-800/50">
              <span className="text-zinc-400 tracking-widest uppercase">Active Positions</span>
              <span className="text-zinc-600">COUNT: {activeTrades.length}</span>
            </div>
            
            <div className="grid grid-cols-6 text-zinc-500 border-b border-zinc-800/30 pb-2 mb-2 px-2 tracking-wide font-medium">
               <span>SYMBOL // RISK</span>
               <span>SIDE // LEVERAGE</span>
               <span>ENTRY // CURRENT</span>
               <span>SIZE // VALUE</span>
               <span>STOP LOSS // TAKE PROFIT</span>
               <span className="text-right">UNREALIZED PnL</span>
            </div>
            
            {activeTrades.length === 0 ? (
              <div className="flex-grow flex items-center justify-center text-zinc-600 text-xs py-8">
                [ NO ACTIVE REAL-TIME TRADES - SCANNING MARKET DATA ]
              </div>
            ) : (
              <div className="space-y-1.5 flex-grow overflow-y-auto">
                {activeTrades.map((t, index) => {
                  const entry = parseFloat(t.entry_price) || 0;
                  const currentPrice = parseFloat(t.current_price) || systemState.prices?.[t.symbol] || entry;
                  const qty = parseFloat(t.qty) || 0;
                  
                  const pnlVal = t.side === 'buy' 
                    ? (currentPrice - entry) * qty 
                    : (entry - currentPrice) * qty;
                  const pnlPct = entry > 0 ? (pnlVal / (entry * qty)) * 100 : 0;
                  const isProfit = pnlVal >= 0;
                  
                  return (
                    <div key={index} className="grid grid-cols-6 items-center px-2 py-2 bg-zinc-950/40 border border-zinc-900/60 hover:border-zinc-800/80 transition-all text-zinc-300 text-[11px]">
                      <div className="flex flex-col">
                        <span className="text-zinc-100 font-semibold">{t.symbol}</span>
                        <span className="text-[9px] text-zinc-500">5% RISK // SPOT-FUT</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span className={`uppercase font-medium text-[9px] px-1.5 py-0.5 rounded border max-w-max leading-none ${t.side === 'buy' ? 'text-emerald-400 bg-emerald-950/20 border-emerald-900/40' : 'text-rose-400 bg-rose-950/20 border-rose-900/40'}`}>
                          {t.side === 'buy' ? 'LONG' : 'SHORT'}
                        </span>
                        <span className="text-[9px] text-zinc-500 mt-1">3.0x EXP LEV</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span>${entry.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                        <span className="text-[9px] text-zinc-400">${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span>{qty.toFixed(5)}</span>
                        <span className="text-[9px] text-zinc-500">${(qty * entry).toFixed(2)} USDT</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span className="text-rose-400/80">SL: ${parseFloat(t.sl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                        <span className="text-emerald-400/80">TP: ${parseFloat(t.tp).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                      </div>
                      
                      <div className="text-right flex flex-col justify-center items-end">
                        <span className={`font-semibold text-xs ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isProfit ? '+' : ''}${pnlVal.toFixed(2)}
                        </span>
                        <span className={`text-[9px] ${isProfit ? 'text-emerald-500' : 'text-rose-500'}`}>
                          {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* SYSTEM LOGS / HEARTBEAT */}
          <div className="bg-[#111111] border border-zinc-800/80 p-4 min-h-[300px] flex flex-col">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-800/50">
              <span className="text-zinc-400 tracking-widest uppercase">System Event Log</span>
              <Shield size={12} className="text-zinc-600" />
            </div>
            
            {logs.length === 0 ? (
              <div className="flex-grow flex items-center justify-center text-zinc-600">
                [ NO SYSTEM EVENTS IN STACK ]
              </div>
            ) : (
              <div className="space-y-2 text-[10px] leading-relaxed text-zinc-400 font-mono overflow-y-auto flex-grow max-h-[250px]">
                {logs.map((log, index) => (
                  <div key={index} className="flex gap-3 hover:bg-zinc-900/30 p-0.5">
                    <span className="text-zinc-600 flex-none">{log.time}</span>
                    <span className="break-all">{log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}

function Metric({ title, value, sub }: any) {
  return (
    <div className="bg-[#111111] border border-zinc-800/80 p-4 flex flex-col justify-between hover:border-zinc-700 transition-colors">
      <span className="text-zinc-500 tracking-widest mb-3">{title}</span>
      <span className="text-xl text-zinc-100 mb-1">{value}</span>
      <span className="text-zinc-600">{sub}</span>
    </div>
  );
}

function Sparkline({ data }: { data: {value: number}[] }) {
  if (!data || data.length === 0) return null;
  const values = data.map(d => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  
  const points = values.map((val, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((val - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full stroke-zinc-600 fill-transparent">
      <polyline points={points} vectorEffect="non-scaling-stroke" strokeWidth="1" />
    </svg>
  );
}
