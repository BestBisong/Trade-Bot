"use client";

import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, Shield, Cpu, Clock, TerminalSquare, X, 
  Settings, Play, Pause, TrendingUp, TrendingDown, 
  DollarSign, Sliders, Trash2, RefreshCw, AlertTriangle, 
  CheckCircle2, ChevronRight, HelpCircle, ArrowUpRight, ArrowDownRight
} from "lucide-react";

// Helper to generate simulated volatility charts
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

interface BotSettings {
  auto_trading_enabled: boolean;
  partial_tp_enabled: boolean;
  dynamic_ml_risk: boolean;
  daily_200sma_guard: boolean;
  trailing_stop_enabled: boolean;
  allow_shorts: boolean;
  risk_per_trade: number;
  max_notional_per_trade: number;
  symbols: string[];
  trend_guard_enabled: boolean;
}

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const [selectedCoin, setSelectedCoin] = useState<string | null>(null);
  const [apiSaving, setApiSaving] = useState(false);
  const [apiClearSaving, setApiClearSaving] = useState(false);
  const [apiCloseSaving, setApiCloseSaving] = useState<string | null>(null);
  
  // Real-time backend states
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
    prices: {} as Record<string, number>,
    settings: {
      auto_trading_enabled: true,
      partial_tp_enabled: false,
      dynamic_ml_risk: false,
      daily_200sma_guard: true,
      trailing_stop_enabled: false,
      allow_shorts: true,
      risk_per_trade: 0.035,
      max_notional_per_trade: 3.0,
      symbols: ["BTC/USDT", "ETH/USDT"],
      trend_guard_enabled: true
    } as BotSettings,
    diagnostics: {} as Record<string, any>
  });
  
  const [activeTrades, setActiveTrades] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [backendOnline, setBackendOnline] = useState(false);
  const [lastScanTime, setLastScanTime] = useState<string>("");

  // Sandbox Mode states (only used if backendOnline = false)
  const [sandboxState, setSandboxState] = useState({
    wallet: 100.0,
    settings: {
      auto_trading_enabled: true,
      partial_tp_enabled: false,
      dynamic_ml_risk: false,
      daily_200sma_guard: true,
      trailing_stop_enabled: false,
      allow_shorts: true,
      risk_per_trade: 0.035,
      max_notional_per_trade: 3.0,
      symbols: ["BTC/USDT", "ETH/USDT"],
      trend_guard_enabled: true
    } as BotSettings,
    activeTrades: [] as any[],
    history: [] as any[],
    logs: [
      { time: new Date().toLocaleTimeString(), message: "SYSTEM | Sandbox terminal started. Awaiting virtual market..." }
    ] as any[],
    prices: {
      'BTC/USDT': 92400,
      'ETH/USDT': 3120
    } as Record<string, number>,
    diagnostics: {
      'BTC/USDT': {
        regime: 'ranging',
        score: 1.5,
        threshold: 2.5,
        ml_prob: 0.52,
        rsi: 42.1,
        rsi_sig: "HOLD",
        sma_sig: "HOLD",
        bb_sig: "BUY",
        market_bullish: false,
        blocked_by: "4H_BEAR_TREND_GUARD"
      },
      'ETH/USDT': {
        regime: 'ranging',
        score: 2.0,
        threshold: 2.5,
        ml_prob: 0.49,
        rsi: 38.5,
        rsi_sig: "BUY",
        sma_sig: "HOLD",
        bb_sig: "BUY",
        market_bullish: false,
        blocked_by: "4H_BEAR_TREND_GUARD"
      }
    } as Record<string, any>
  });

  // Sparkline state caches to keep line drawing stable
  const [sparklines] = useState(() => ({
    'BTC/USDT': generateData(92400, 200),
    'ETH/USDT': generateData(3120, 15)
  }));

  // Fetch API endpoint helper
  const getApiUrl = () => {
    return process.env.NEXT_PUBLIC_API_URL || 
      (typeof window !== 'undefined' 
        ? (window.location.port === '3000' 
            ? `${window.location.protocol}//${window.location.hostname}:8000` 
            : '') 
        : 'http://127.0.0.1:8000');
  };

  useEffect(() => {
    setMounted(true);
    
    const fetchAllData = async () => {
      try {
        const apiBase = getApiUrl();
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
          setLastScanTime(new Date().toLocaleTimeString());
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

  // Sandbox Mode Engine (runs when backend is offline)
  useEffect(() => {
    if (backendOnline) return;

    const sandboxTimer = setInterval(() => {
      setSandboxState(prev => {
        const newPrices = {
          'BTC/USDT': prev.prices['BTC/USDT'] + (Math.random() - 0.5) * 120,
          'ETH/USDT': prev.prices['ETH/USDT'] + (Math.random() - 0.5) * 10
        };

        const currentSettings = prev.settings;
        const newLogs = [...prev.logs];
        const newActiveTrades = [...prev.activeTrades];
        const newHistory = [...prev.history];
        let newWallet = prev.wallet;

        // Perform Simulated Scan Cycle every 6 seconds
        const seconds = new Date().getSeconds();
        const isScanCycle = seconds % 6 === 0;
        const updatedDiagnostics = { ...prev.diagnostics };

        if (isScanCycle && currentSettings.auto_trading_enabled) {
          Object.keys(COIN_CONFIGS).forEach(symbol => {
            // Check if position already open
            if (newActiveTrades.some(t => t.symbol === symbol)) {
              updatedDiagnostics[symbol] = {
                regime: 'ranging',
                score: 0.0,
                threshold: 2.5,
                ml_prob: 0.5,
                rsi: 50.0,
                rsi_sig: "HOLD",
                sma_sig: "HOLD",
                bb_sig: "HOLD",
                market_bullish: false,
                blocked_by: "POSITION_ALREADY_OPEN"
              };
              return;
            }

            // Simulate market conditions
            // 90% of the time, simulate "ranging/choppy" (bad market), which matches current market conditions.
            const regime = Math.random() > 0.85 ? 'trending' : 'ranging';
            const market_bullish = Math.random() > 0.6; // Bearish bias matches 4-month bad market
            const ml_prob = 0.42 + Math.random() * 0.16; // Centers around 0.50 (low confidence)
            const rsi = 30 + Math.random() * 40;
            
            // Build indicators
            const rsi_sig = rsi < 35 ? "BUY" : (rsi > 65 ? "SELL" : "HOLD");
            const bb_sig = rsi < 38 ? "BUY" : (rsi > 62 ? "SELL" : "HOLD");
            const sma_sig = Math.random() > 0.7 ? (market_bullish ? "BUY" : "SELL") : "HOLD";

            let score = 0.0;
            if (regime === 'ranging') {
              if (rsi_sig === "BUY") score += 2.0;
              if (bb_sig === "BUY") score += 2.5;
            } else {
              if (market_bullish) score += 2.0;
              if (sma_sig === "BUY") score += 2.0;
            }

            // ML confidence booster
            const ml_long_threshold = regime === 'ranging' ? 0.55 : 0.58;
            if (ml_prob >= ml_long_threshold) score += 2.0;
            else if (ml_prob <= 0.45) score -= 2.0;

            const threshold = regime === 'ranging' ? 2.5 : 3.0;
            let signal = "HOLD";
            if (score >= threshold) signal = "BUY";
            else if (score <= -threshold) signal = "SELL";

            let blockedReason = null;

            if (signal === "BUY") {
              // Apply Guards
              if (currentSettings.daily_200sma_guard && !market_bullish) {
                blockedReason = "DAILY_200SMA_GUARD";
              } else if (currentSettings.trend_guard_enabled && regime === 'trending' && !market_bullish) {
                blockedReason = "4H_BEAR_TREND_GUARD";
              }
            } else if (signal === "SELL") {
              if (!currentSettings.allow_shorts) {
                blockedReason = "SHORTS_DISABLED";
              } else if (currentSettings.daily_200sma_guard && market_bullish) {
                blockedReason = "DAILY_200SMA_GUARD";
              } else if (currentSettings.trend_guard_enabled && regime === 'trending' && market_bullish) {
                blockedReason = "4H_BULL_TREND_GUARD";
              }
            } else {
              blockedReason = "INSUFFICIENT_SCORE";
            }

            updatedDiagnostics[symbol] = {
              regime,
              score,
              threshold,
              ml_prob,
              rsi,
              rsi_sig,
              sma_sig,
              bb_sig,
              market_bullish,
              blocked_by: blockedReason
            };

            // If a trade passes all filters, execute it!
            if (signal !== "HOLD" && !blockedReason) {
              const entry_price = newPrices[symbol as keyof typeof newPrices];
              const qty = currentSettings.max_notional_per_trade / entry_price;
              const sl_dist = entry_price * 0.05; // 5% sl
              const sl = signal === "BUY" ? entry_price - sl_dist : entry_price + sl_dist;
              const tp = signal === "BUY" ? entry_price + sl_dist * 2.0 : entry_price - sl_dist * 2.0;

              newActiveTrades.push({
                symbol,
                side: signal.toLowerCase(),
                entry_price,
                current_price: entry_price,
                qty,
                sl,
                tp,
                opened_at: new Date().toLocaleTimeString(),
                half_tp: signal === "BUY" ? entry_price + sl_dist : entry_price - sl_dist,
                has_scaled_out: false,
                accumulated_pnl: 0.0
              });

              newLogs.unshift({
                time: new Date().toLocaleTimeString(),
                message: `OPENED | ${signal} ${symbol} | regime: ${regime.toUpperCase()} | Entry: $${entry_price.toFixed(2)} | Qty: ${qty.toFixed(4)}`
              });
            } else if (signal !== "HOLD" && blockedReason) {
              // Log that a trade was generated but BLOCKED by a guard
              if (Math.random() > 0.4) {
                newLogs.unshift({
                  time: new Date().toLocaleTimeString(),
                  message: `GUARD | ${symbol} ${signal} Signal generated but blocked by ${blockedReason}`
                });
              }
            }
          });
        }

        // Simulate price updates for active trades and evaluate closures
        for (let i = newActiveTrades.length - 1; i >= 0; i--) {
          const trade = newActiveTrades[i];
          const curPrice = newPrices[trade.symbol as keyof typeof newPrices];
          trade.current_price = curPrice;

          const isBuy = trade.side === "buy";
          const pnlVal = isBuy ? (curPrice - trade.entry_price) * trade.qty : (trade.entry_price - curPrice) * trade.qty;
          
          const hitTP = isBuy ? curPrice >= trade.tp : curPrice <= trade.tp;
          const hitSL = isBuy ? curPrice <= trade.sl : curPrice >= trade.sl;

          // Check partial TP in mock mode
          if (currentSettings.partial_tp_enabled && !trade.has_scaled_out) {
            const hitHalfTP = isBuy ? curPrice >= trade.half_tp : curPrice <= trade.half_tp;
            if (hitHalfTP) {
              const realizedPnl = (isBuy ? (trade.half_tp - trade.entry_price) : (trade.entry_price - trade.half_tp)) * (trade.qty * 0.5);
              newWallet += realizedPnl;
              trade.qty = trade.qty * 0.5;
              trade.sl = trade.entry_price; // move sl to breakeven
              trade.has_scaled_out = true;
              trade.accumulated_pnl = realizedPnl;
              newLogs.unshift({
                time: new Date().toLocaleTimeString(),
                message: `SCALED OUT | ${trade.symbol} | Locked half profit: $${realizedPnl.toFixed(2)} | Moved SL to Breakeven`
              });
            }
          }

          if (hitTP || hitSL) {
            const finalPnl = pnlVal + trade.accumulated_pnl;
            newWallet += isBuy ? (curPrice - trade.entry_price) * trade.qty : (trade.entry_price - curPrice) * trade.qty;
            
            newHistory.unshift({
              symbol: trade.symbol,
              pnl: finalPnl,
              reason: hitTP ? "tp" : "sl",
              closed_at: new Date().toISOString()
            });

            newLogs.unshift({
              time: new Date().toLocaleTimeString(),
              message: `CLOSED | ${trade.symbol} | Reason: ${hitTP ? 'TP' : 'SL'} | PnL: $${finalPnl.toFixed(2)} | Wallet: $${newWallet.toFixed(2)}`
            });

            newActiveTrades.splice(i, 1);
          }
        }

        return {
          ...prev,
          prices: newPrices,
          activeTrades: newActiveTrades,
          history: newHistory,
          wallet: newWallet,
          logs: newLogs.slice(0, 30),
          diagnostics: updatedDiagnostics
        };
      });
      setLastScanTime(new Date().toLocaleTimeString());
    }, 2000);

    return () => clearInterval(sandboxTimer);
  }, [backendOnline]);

  const activeSettings = backendOnline ? systemState.settings : sandboxState.settings;
  const activePrices = backendOnline ? systemState.prices : sandboxState.prices;
  const activeDiagnostics = backendOnline ? systemState.diagnostics : sandboxState.diagnostics;
  const activeWallet = backendOnline ? systemState.wallet : sandboxState.wallet;
  const activeTradesList = backendOnline ? activeTrades : sandboxState.activeTrades;
  const activeHistoryList = backendOnline ? history : sandboxState.history;
  const activeLogsList = backendOnline ? logs : sandboxState.logs;

  // Handler to Save Settings
  const saveSettings = async (updatedSettings: BotSettings) => {
    if (backendOnline) {
      setApiSaving(true);
      try {
        const apiBase = getApiUrl();
        const res = await fetch(`${apiBase}/api/settings`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updatedSettings)
        });
        if (res.ok) {
          const data = await res.json();
          setSystemState(prev => ({ ...prev, settings: data.settings }));
        }
      } catch (e) {
        console.error("Failed to save settings to API: ", e);
      } finally {
        setApiSaving(false);
      }
    } else {
      setSandboxState(prev => {
        const updatedLogs = [
          { time: new Date().toLocaleTimeString(), message: "CONFIG | Dynamic settings hot-reloaded in Sandbox." },
          ...prev.logs
        ];
        return {
          ...prev,
          settings: updatedSettings,
          logs: updatedLogs.slice(0, 30)
        };
      });
    }
  };

  // Handler to Close Positions Manually
  const closePosition = async (symbol: string) => {
    if (backendOnline) {
      setApiCloseSaving(symbol);
      try {
        const apiBase = getApiUrl();
        const res = await fetch(`${apiBase}/api/close`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol })
        });
        if (res.ok) {
          // Instantly fetch updated trades
          const tradesRes = await fetch(`${apiBase}/api/trades`);
          if (tradesRes.ok) {
            setActiveTrades(await tradesRes.json());
          }
        }
      } catch (e) {
        console.error("Failed to close position via API: ", e);
      } finally {
        setApiCloseSaving(null);
      }
    } else {
      setSandboxState(prev => {
        const tradeIndex = prev.activeTrades.findIndex(t => t.symbol === symbol);
        if (tradeIndex === -1) return prev;
        
        const trade = prev.activeTrades[tradeIndex];
        const curPrice = prev.prices[symbol];
        const isBuy = trade.side === "buy";
        const finalPnl = (isBuy ? (curPrice - trade.entry_price) : (trade.entry_price - curPrice)) * trade.qty + trade.accumulated_pnl;

        const updatedActive = prev.activeTrades.filter(t => t.symbol !== symbol);
        const updatedHistory = [
          { symbol, pnl: finalPnl, reason: "manual_close", closed_at: new Date().toISOString() },
          ...prev.history
        ];
        const updatedLogs = [
          { time: new Date().toLocaleTimeString(), message: `COMMAND | Manual Close Request for ${symbol} processed. PnL: $${finalPnl.toFixed(2)}` },
          ...prev.logs
        ];

        return {
          ...prev,
          activeTrades: updatedActive,
          history: updatedHistory,
          wallet: prev.wallet + (isBuy ? (curPrice - trade.entry_price) * trade.qty : (trade.entry_price - curPrice) * trade.qty),
          logs: updatedLogs.slice(0, 30)
        };
      });
    }
  };

  // Handler to Clear completed trade history
  const clearHistory = async () => {
    if (backendOnline) {
      setApiClearSaving(true);
      try {
        const apiBase = getApiUrl();
        const res = await fetch(`${apiBase}/api/clear-history`, {
          method: "POST"
        });
        if (res.ok) {
          setHistory([]);
        }
      } catch (e) {
        console.error("Failed to clear history via API: ", e);
      } finally {
        setApiClearSaving(false);
      }
    } else {
      setSandboxState(prev => ({
        ...prev,
        history: [],
        logs: [
          { time: new Date().toLocaleTimeString(), message: "SYSTEM | Sandbox trade history cleared." },
          ...prev.logs
        ].slice(0, 30)
      }));
    }
  };

  const toggleSetting = (key: keyof BotSettings) => {
    const nextSettings = {
      ...activeSettings,
      [key]: !activeSettings[key]
    };
    saveSettings(nextSettings);
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    const nextSettings = {
      ...activeSettings,
      risk_per_trade: val / 100
    };
    saveSettings(nextSettings);
  };

  const handleNotionalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value) || 1.0;
    const nextSettings = {
      ...activeSettings,
      max_notional_per_trade: val
    };
    saveSettings(nextSettings);
  };

  if (!mounted) return null;

  // Quick Diagnostics Recommendation logic
  const getAdvisoryMessage = (symbol: string, diag: any) => {
    if (!diag) return "Scanning market data for trade signals...";
    const { blocked_by, regime, score, threshold } = diag;
    
    if (!activeSettings.auto_trading_enabled) {
      return "The auto-trading scanner is paused. Toggle it ON in the console to allow automatic scans.";
    }
    
    if (blocked_by === "DAILY_200SMA_GUARD") {
      return `⚠️ BLOCKED BY 200 DAILY SMA: The price is currently in a macro downtrend. To authorize trades in a bear market, disable the "Daily 200 SMA Guard" in the Strategy Console.`;
    }
    if (blocked_by === "4H_BEAR_TREND_GUARD" || blocked_by === "4H_BULL_TREND_GUARD") {
      return `⚠️ BLOCKED BY 4H TREND GUARD: Trend filters are restricting trades against the 4H bias. Disable the "4H Trend Guard" in the Console to authorize entries in choppy/ranging markets.`;
    }
    if (blocked_by === "INSUFFICIENT_SCORE") {
      return `ℹ️ INSUFFICIENT SCORE: Signals do not fully align. Score is ${score} (Threshold is ${threshold}). In sideways markets, consider turning off trend filters or lowering ML constraints to increase scan sensitivity.`;
    }
    if (blocked_by === "SHORTS_DISABLED" && diag.sma_sig === "SELL") {
      return `ℹ️ SELL SIGNAL DETECTED: The bot wants to open a SHORT position, but shorts are disabled. Enable "Allow Short Positions" in the Strategy Console.`;
    }
    if (blocked_by === "POSITION_ALREADY_OPEN") {
      return `✅ POSITION OPEN: An active position is already running for this symbol. Waiting for TP/SL exit before scanning new entries.`;
    }
    if (blocked_by === "MAX_POSITIONS_REACHED") {
      return `⚠️ RISK SHIELD: Maximum position limit reached. Close an active trade manually or wait for execution before scanning new entries.`;
    }
    return `✅ SCAN ACTIVE: Auto-trading scanner is running. Price regime is "${regime.toUpperCase()}" with score ${score}/${threshold}.`;
  };

  return (
    <div className="min-h-screen bg-[#060608] text-zinc-300 font-mono p-4 selection:bg-zinc-800 text-xs">
      <div className="max-w-[1850px] mx-auto space-y-4">
        
        {/* HUD HEADER */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-900 bg-[#0c0c10]/40 p-4 rounded-xl backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center">
              <span className={`absolute inline-flex h-2.5 w-2.5 rounded-full opacity-75 animate-ping ${backendOnline ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${backendOnline ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold tracking-widest text-zinc-100 uppercase">J.A.R.V.I.S // QUANT WORKSTATION</h1>
                <span className="text-[9px] text-[#8b5cf6] border border-[#8b5cf6]/30 px-1 py-0.2 rounded bg-[#8b5cf6]/5 uppercase">v2.1 Adaptive</span>
              </div>
              <p className="text-[10px] text-zinc-500 mt-0.5">Automated Multi-Regime Trading Engine & Guard Diagnostics</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-zinc-500">
            <span className="flex items-center gap-2 bg-[#121218] border border-zinc-900 px-3 py-1.5 rounded-lg">
              <span className="text-[10px] text-zinc-600 font-semibold">FEED:</span>
              <span className={backendOnline ? "text-emerald-400 font-bold" : "text-amber-500 font-bold"}>
                {backendOnline ? "LIVE API CONNECTED" : "SANDBOX SIMULATION"}
              </span>
            </span>
            <span className="flex items-center gap-2">
              <Clock size={12} className="text-zinc-600" /> UTC: {new Date().toISOString().split('T')[1].split('.')[0]}
            </span>
            <span className="flex items-center gap-2">
              <Activity size={12} className="text-zinc-600" /> Latency: {backendOnline ? '4ms' : '0ms'}
            </span>
            <span className="flex items-center gap-2">
              <Cpu size={12} className="text-zinc-600" /> CPU Load: {backendOnline ? '6%' : '1%'}
            </span>
          </div>
        </header>

        {/* METRICS PANEL */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Metric 
            title="TOTAL CAPITAL" 
            value={`$${activeWallet.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} 
            sub={backendOnline ? `${systemState.risk.daily_pnl_pct.toFixed(2)}% TODAY` : "VIRTUAL DEMO WALLET"}
            subColor={backendOnline && systemState.risk.daily_pnl_pct >= 0 ? "text-emerald-400" : (backendOnline ? "text-rose-400" : "text-zinc-500")}
          />
          <Metric 
            title="SYSTEM SCAN STATUS" 
            value={activeSettings.auto_trading_enabled ? "AUTO-SCANNING" : "SCANNER PAUSED"} 
            sub={activeSettings.auto_trading_enabled ? `CYCLE: EVERY 10s | LAST: ${lastScanTime || 'NEVER'}` : "AUTOPILOT IN STANDBY"}
            subColor={activeSettings.auto_trading_enabled ? "text-emerald-400" : "text-amber-500"}
          />
          <Metric 
            title="PORTFOLIO TRADES" 
            value={backendOnline ? `${systemState.risk.wins_today}W - ${systemState.risk.losses_today}L` : `${activeHistoryList.filter(h => h.pnl > 0).length}W - ${activeHistoryList.filter(h => h.pnl <= 0).length}L`} 
            sub={backendOnline ? `WIN RATE: ${systemState.risk.win_rate.toFixed(1)}%` : `WIN RATE: ${activeHistoryList.length > 0 ? ((activeHistoryList.filter(h => h.pnl > 0).length / activeHistoryList.length) * 100).toFixed(1) : '0.0'}%`}
            subColor="text-[#8b5cf6]"
          />
          <Metric 
            title="ACTIVE RISK SHIELD" 
            value={backendOnline && systemState.risk.cooldown_until ? "COOLDOWN SHIELD" : "GUARD NORMAL"} 
            sub={backendOnline && systemState.risk.cooldown_until ? `COOLDOWN ACTIVE` : "STABLE REGIME TARGETING"}
            subColor={backendOnline && systemState.risk.cooldown_until ? "text-rose-500" : "text-emerald-400"}
          />
        </div>

        {/* WORKSTATION GRID */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          
          {/* LEFT SECTION - SCANNER DIAGNOSTICS & ADVISORY (2/3 width) */}
          <div className="lg:col-span-2 space-y-4">
            
            {/* COIN SCANNERS & LIVE INDICATORS */}
            <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-4 space-y-4 shadow-xl">
              <div className="flex justify-between items-center pb-2 border-b border-zinc-900">
                <div className="flex items-center gap-2">
                  <TerminalSquare size={14} className="text-zinc-500" />
                  <span className="font-bold tracking-widest text-zinc-200 uppercase">Live Market Scanner & Guard Verdicts</span>
                </div>
                <span className="text-[10px] text-zinc-500 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  Diagnostics stream active
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.keys(COIN_CONFIGS).map((symbol) => {
                  const isSelected = selectedCoin === symbol;
                  const livePrice = activePrices?.[symbol] || COIN_CONFIGS[symbol].price;
                  const diag = activeDiagnostics?.[symbol];
                  const regime = diag?.regime || "ranging";
                  const score = diag?.score || 0.0;
                  const threshold = diag?.threshold || 2.5;
                  const isBlocked = diag?.blocked_by && diag.blocked_by !== "POSITION_ALREADY_OPEN";
                  const isOpened = diag?.blocked_by === "POSITION_ALREADY_OPEN";

                  return (
                    <div 
                      key={symbol}
                      onClick={() => setSelectedCoin(isSelected ? null : symbol)}
                      className={`bg-[#0d0d12] border rounded-lg p-4 relative flex flex-col transition-all cursor-pointer select-none group hover:bg-[#12121a]/30 ${isSelected ? 'border-[#8b5cf6] ring-1 ring-[#8b5cf6]/20' : 'border-zinc-900'}`}
                    >
                      {/* Badge / Header */}
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <span className="text-zinc-100 font-bold text-sm tracking-wide block">{symbol}</span>
                          <span className={`px-1.5 py-0.5 mt-1 inline-block rounded text-[9px] font-bold uppercase tracking-wider ${
                            regime === "trending" ? "bg-emerald-950/40 text-emerald-400 border border-emerald-900/30" : 
                            (regime === "volatile" ? "bg-rose-950/40 text-rose-400 border border-rose-900/30" : 
                            "bg-amber-950/40 text-amber-400 border border-amber-900/30")
                          }`}>
                            {regime.toUpperCase()} REGIME
                          </span>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] text-zinc-600 block">LIVE VALUE</span>
                          <span className="text-sm text-zinc-100 font-semibold font-mono">
                            ${livePrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>

                      {/* Sparkline background */}
                      <div className="h-10 opacity-15 my-2">
                        <Sparkline data={sparklines[symbol as keyof typeof sparklines]} />
                      </div>

                      {/* Guard status summary */}
                      <div className="mt-auto pt-3 border-t border-zinc-900 flex justify-between items-center">
                        <div className="flex items-center gap-1.5">
                          {isBlocked ? (
                            <span className="h-2 w-2 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50"></span>
                          ) : (isOpened ? (
                            <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50"></span>
                          ) : (
                            <span className="h-2 w-2 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50"></span>
                          ))}
                          <span className={`text-[10px] uppercase font-bold tracking-wider ${isBlocked ? 'text-rose-400' : (isOpened ? 'text-emerald-400' : 'text-amber-400')}`}>
                            {isBlocked ? "Blocked by Guard" : (isOpened ? "Active Position" : "Pending Alignment")}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-[10px] text-zinc-500">
                          <span>Verdict:</span>
                          <span className="font-semibold text-zinc-300">{(diag?.blocked_by || "HOLD").replace("_", " ")}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ADVISORY & EXPLAINABILITY DRAWER */}
            <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-5 space-y-4 shadow-xl">
              <div className="flex items-center justify-between pb-2 border-b border-zinc-900">
                <div className="flex items-center gap-2">
                  <HelpCircle size={14} className="text-[#8b5cf6]" />
                  <span className="font-bold tracking-widest text-zinc-200 uppercase">Adaptive Guard & Explainability Panel</span>
                </div>
                <span className="text-[9px] text-[#8b5cf6] font-bold">EXPLAINABLE AI // DIAGNOSE WHY BOT ISN&apos;T TRADING</span>
              </div>

              <div className="space-y-4">
                {Object.keys(COIN_CONFIGS).map(symbol => {
                  const diag = activeDiagnostics?.[symbol];
                  const regime = diag?.regime || "ranging";
                  const score = diag?.score || 0.0;
                  const threshold = diag?.threshold || 2.5;
                  const mlConf = diag?.ml_prob ? (diag.ml_prob * 100).toFixed(1) : "50.0";
                  const rsi = diag?.rsi ? diag.rsi.toFixed(1) : "50.0";
                  
                  return (
                    <div key={symbol} className="bg-[#0e0e13] border border-zinc-900 rounded-lg p-4 space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-zinc-200">{symbol} Diagnose</span>
                        <div className="flex items-center gap-4 text-[10px]">
                          <span className="text-zinc-500">Regime: <strong className="text-zinc-300">{regime.toUpperCase()}</strong></span>
                          <span className="text-zinc-500">Score: <strong className="text-zinc-300">{score}/{threshold}</strong></span>
                          <span className="text-zinc-500">ML Confidence: <strong className="text-zinc-300">{mlConf}%</strong></span>
                        </div>
                      </div>

                      {/* Technical alignment metrics */}
                      <div className="grid grid-cols-4 gap-2 text-[10px] bg-zinc-950/50 p-2 rounded border border-zinc-900/60">
                        <div className="text-center border-r border-zinc-900">
                          <span className="text-zinc-500 block">RSI ({rsi})</span>
                          <span className={`font-semibold ${diag?.rsi_sig === "BUY" ? "text-emerald-400" : (diag?.rsi_sig === "SELL" ? "text-rose-400" : "text-zinc-400")}`}>
                            {diag?.rsi_sig || "HOLD"}
                          </span>
                        </div>
                        <div className="text-center border-r border-zinc-900">
                          <span className="text-zinc-500 block">Bollinger Band</span>
                          <span className={`font-semibold ${diag?.bb_sig === "BUY" ? "text-emerald-400" : (diag?.bb_sig === "SELL" ? "text-rose-400" : "text-zinc-400")}`}>
                            {diag?.bb_sig || "HOLD"}
                          </span>
                        </div>
                        <div className="text-center border-r border-zinc-900">
                          <span className="text-zinc-500 block">MACD / SMA</span>
                          <span className={`font-semibold ${diag?.sma_sig === "BUY" ? "text-emerald-400" : (diag?.sma_sig === "SELL" ? "text-rose-400" : "text-zinc-400")}`}>
                            {diag?.sma_sig || "HOLD"}
                          </span>
                        </div>
                        <div className="text-center">
                          <span className="text-zinc-500 block">4H Trend Bias</span>
                          <span className={`font-semibold ${diag?.market_bullish ? "text-emerald-400" : "text-rose-400"}`}>
                            {diag?.market_bullish ? "BULLISH" : "BEARISH"}
                          </span>
                        </div>
                      </div>

                      {/* Diagnostic Explainer */}
                      <div className={`p-3 rounded-lg flex items-start gap-3 border ${
                        diag?.blocked_by && diag.blocked_by !== "POSITION_ALREADY_OPEN" 
                          ? "bg-rose-950/10 border-rose-900/30 text-rose-200/90" 
                          : (diag?.blocked_by === "POSITION_ALREADY_OPEN" 
                            ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-200/90" 
                            : "bg-zinc-950/60 border-zinc-900 text-zinc-400")
                      }`}>
                        <div className="mt-0.5">
                          {diag?.blocked_by && diag.blocked_by !== "POSITION_ALREADY_OPEN" ? (
                            <AlertTriangle size={14} className="text-rose-500 flex-none" />
                          ) : (diag?.blocked_by === "POSITION_ALREADY_OPEN" ? (
                            <CheckCircle2 size={14} className="text-emerald-500 flex-none" />
                          ) : (
                            <Activity size={14} className="text-zinc-500 flex-none" />
                          ))}
                        </div>
                        <div className="leading-relaxed text-[11px]">
                          {getAdvisoryMessage(symbol, diag)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>

          {/* RIGHT SECTION - STRATEGY OPTIMIZATION CONSOLE (1/3 width) */}
          <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-5 shadow-xl space-y-4">
            <div className="flex items-center gap-2 pb-2 border-b border-zinc-900">
              <Sliders size={14} className="text-[#8b5cf6]" />
              <span className="font-bold tracking-widest text-zinc-200 uppercase">Auto-Trading Optimizer</span>
            </div>

            <p className="text-[10px] text-zinc-500 leading-relaxed">
              Dynamically bypass trend guards in choppy/ranging markets to authorize the mean-reversion scanner to place trades immediately.
            </p>

            <div className="space-y-4 pt-2">
              
              {/* TOGGLES */}
              <div className="space-y-2.5">
                <ConsoleToggle 
                  label="Scanner Auto-Trading" 
                  description="Toggle the automatic market scanner loop"
                  active={activeSettings.auto_trading_enabled}
                  onChange={() => toggleSetting("auto_trading_enabled")}
                />
                
                <ConsoleToggle 
                  label="Daily 200 SMA Guard" 
                  description="Restricts buys below daily 200 SMA (Bear Protection)"
                  active={activeSettings.daily_200sma_guard}
                  onChange={() => toggleSetting("daily_200sma_guard")}
                  isGuard={true}
                />

                <ConsoleToggle 
                  label="4H Trend Guard" 
                  description="Restricts counter-trend entries based on 4H MACD"
                  active={activeSettings.trend_guard_enabled}
                  onChange={() => toggleSetting("trend_guard_enabled")}
                  isGuard={true}
                />

                <ConsoleToggle 
                  label="Allow Short Positions" 
                  description="Allows opening short positions in bearish trends"
                  active={activeSettings.allow_shorts}
                  onChange={() => toggleSetting("allow_shorts")}
                />

                <ConsoleToggle 
                  label="Trailing ATR Stop Loss" 
                  description="Dynamically raises stop loss using 3x rolling ATR"
                  active={activeSettings.trailing_stop_enabled}
                  onChange={() => toggleSetting("trailing_stop_enabled")}
                />

                <ConsoleToggle 
                  label="Partial Profit Scale-out" 
                  description="Locks 50% profit at 1:1 RR and moves SL to breakeven"
                  active={activeSettings.partial_tp_enabled}
                  onChange={() => toggleSetting("partial_tp_enabled")}
                />

                <ConsoleToggle 
                  label="Dynamic ML Risk Sizing" 
                  description="Sizes risk (3% - 6.5%) based on brain confidence"
                  active={activeSettings.dynamic_ml_risk}
                  onChange={() => toggleSetting("dynamic_ml_risk")}
                />
              </div>

              {/* SLIDERS & NUMBERS */}
              <div className="space-y-3 pt-3 border-t border-zinc-900">
                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-zinc-400 font-semibold">Flat Risk Per Trade</span>
                    <span className="text-[#8b5cf6] font-bold">{(activeSettings.risk_per_trade * 100).toFixed(1)}%</span>
                  </div>
                  <input 
                    type="range" 
                    min="1.0" 
                    max="10.0" 
                    step="0.5"
                    value={activeSettings.risk_per_trade * 100}
                    onChange={handleSliderChange}
                    className="w-full h-1 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#8b5cf6]"
                  />
                  <span className="text-[9px] text-zinc-600 block mt-0.5">Budget percentage exposed per SL distance</span>
                </div>

                <div>
                  <div className="flex justify-between text-[11px] mb-1">
                    <span className="text-zinc-400 font-semibold">Max Position Size Limit</span>
                    <span className="text-zinc-300 font-bold">${activeSettings.max_notional_per_trade.toFixed(2)} USDT</span>
                  </div>
                  <div className="relative flex items-center">
                    <span className="absolute left-3 text-zinc-600">$</span>
                    <input 
                      type="number" 
                      min="1.0" 
                      max="10.0" 
                      value={activeSettings.max_notional_per_trade}
                      onChange={handleNotionalChange}
                      className="w-full bg-zinc-950 border border-zinc-900 rounded px-7 py-1.5 focus:border-[#8b5cf6] focus:outline-none text-zinc-300"
                    />
                  </div>
                  <span className="text-[9px] text-zinc-600 block mt-0.5">Absolute maximum cost allowed per simulated order</span>
                </div>
              </div>

              {/* SAVE / UPDATE BUTTON */}
              {backendOnline && (
                <button 
                  onClick={() => saveSettings(activeSettings)}
                  disabled={apiSaving}
                  className="w-full mt-2 bg-[#8b5cf6] hover:bg-[#7c3aed] text-zinc-100 font-bold py-2 rounded-lg transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-[#8b5cf6]/15 hover:shadow-[#8b5cf6]/25 disabled:opacity-50"
                >
                  {apiSaving ? (
                    <>
                      <RefreshCw size={12} className="animate-spin" /> Saving Settings...
                    </>
                  ) : (
                    "Save Strategy Adjustments"
                  )}
                </button>
              )}

              {!backendOnline && (
                <div className="p-2 border border-dashed border-amber-900/30 bg-amber-950/5 rounded text-amber-500/80 text-[10px] text-center leading-relaxed">
                  🔧 Running in local Sandbox simulation. All settings hot-reload immediately!
                </div>
              )}

            </div>
          </div>

        </div>

        {/* POSITIONS & HISTORIES */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          
          {/* ACTIVE POSITIONS TABLE (2/3 width) */}
          <div className="lg:col-span-2 bg-[#0b0b0e] border border-zinc-900 rounded-xl p-4 shadow-xl flex flex-col min-h-[300px]">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-900">
              <div className="flex items-center gap-2">
                <Shield size={14} className="text-zinc-500" />
                <span className="font-bold tracking-widest text-zinc-200 uppercase">Active Running Trades</span>
              </div>
              <span className="text-zinc-500 bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900 font-semibold text-[10px]">
                POSITIONS: {activeTradesList.length}
              </span>
            </div>
            
            <div className="grid grid-cols-6 text-zinc-500 border-b border-zinc-900 pb-2 mb-2 px-2 tracking-wide font-medium mt-3 text-[10px]">
               <span>SYMBOL / SIDE</span>
               <span>ENTRY / CURRENT</span>
               <span>SIZE / COST</span>
               <span>STOP / TAKE PROFIT</span>
               <span className="text-right">UNREALIZED PnL</span>
               <span className="text-right">ACTION</span>
            </div>
            
            {activeTradesList.length === 0 ? (
              <div className="flex-grow flex flex-col items-center justify-center text-zinc-600 text-xs py-12 space-y-2 border border-dashed border-zinc-900/40 rounded-lg bg-zinc-950/10">
                <span>[ NO ACTIVE REAL-TIME POSITIONS RUNNING ]</span>
                <span className="text-[10px] text-zinc-700">The automatic scanner will place a trade once filters align, or you can bypass guards to trade immediately.</span>
              </div>
            ) : (
              <div className="space-y-1.5 flex-grow overflow-y-auto max-h-[300px]">
                {activeTradesList.map((t, index) => {
                  const entry = parseFloat(t.entry_price) || 0;
                  const currentPrice = parseFloat(t.current_price) || activePrices?.[t.symbol] || entry;
                  const qty = parseFloat(t.qty) || 0;
                  
                  const pnlVal = t.side === 'buy' 
                    ? (currentPrice - entry) * qty 
                    : (entry - currentPrice) * qty;
                  const pnlPct = entry > 0 ? (pnlVal / (entry * qty)) * 100 : 0;
                  const isProfit = pnlVal >= 0;
                  
                  return (
                    <div key={index} className="grid grid-cols-6 items-center px-2 py-2 bg-[#0e0e13] border border-zinc-900/80 rounded hover:bg-[#12121a]/20 transition-all text-zinc-300 text-[11px]">
                      <div className="flex flex-col">
                        <span className="text-zinc-100 font-semibold">{t.symbol}</span>
                        <span className={`uppercase font-bold text-[8px] tracking-widest mt-0.5 max-w-max leading-none ${t.side === 'buy' ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {t.side === 'buy' ? '● LONG' : '● SHORT'}
                        </span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span>${entry.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                        <span className="text-[9px] text-zinc-500">${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span>{qty.toFixed(5)}</span>
                        <span className="text-[9px] text-zinc-500">${(qty * entry).toFixed(2)} USDT</span>
                      </div>
                      
                      <div className="flex flex-col">
                        <span className="text-rose-400/80">SL: ${parseFloat(t.sl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        <span className="text-emerald-400/80">TP: ${parseFloat(t.tp).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                      </div>
                      
                      <div className="text-right flex flex-col justify-center items-end pr-2">
                        <span className={`font-semibold text-xs ${isProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {isProfit ? '+' : ''}${pnlVal.toFixed(2)}
                        </span>
                        <span className={`text-[9px] ${isProfit ? 'text-emerald-500' : 'text-rose-500'}`}>
                          {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                        </span>
                      </div>

                      <div className="text-right flex items-center justify-end">
                        <button
                          onClick={() => closePosition(t.symbol)}
                          disabled={apiCloseSaving === t.symbol}
                          className="bg-rose-950/20 hover:bg-rose-900/30 text-rose-400 hover:text-rose-300 border border-rose-950/60 rounded px-2.5 py-1 transition-all cursor-pointer disabled:opacity-50 text-[10px]"
                        >
                          {apiCloseSaving === t.symbol ? (
                            <RefreshCw size={10} className="animate-spin" />
                          ) : (
                            "CLOSE"
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* COMPLETED TRADES HISTORY (1/3 width) */}
          <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-4 shadow-xl flex flex-col min-h-[300px]">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-900">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-zinc-500" />
                <span className="font-bold tracking-widest text-zinc-200 uppercase">Completed Trades</span>
              </div>
              
              {activeHistoryList.length > 0 && (
                <button
                  onClick={clearHistory}
                  disabled={apiClearSaving}
                  className="text-zinc-500 hover:text-rose-400 flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Trash2 size={10} /> Clear
                </button>
              )}
            </div>

            {activeHistoryList.length === 0 ? (
              <div className="flex-grow flex items-center justify-center text-zinc-600 text-xs py-12">
                [ NO TRADE HISTORY YET ]
              </div>
            ) : (
              <div className="mt-3 space-y-2 overflow-y-auto max-h-[220px] flex-grow pr-1">
                {activeHistoryList.map((item, idx) => {
                  const pnl = parseFloat(item.pnl) || 0;
                  const isProfit = pnl >= 0;
                  return (
                    <div key={idx} className="bg-zinc-950/60 border border-zinc-900/80 rounded p-2 flex justify-between items-center text-[10px]">
                      <div>
                        <span className="font-bold text-zinc-300">{item.symbol}</span>
                        <div className="flex items-center gap-2 text-zinc-600 text-[8px] mt-0.5 uppercase">
                          <span>{item.reason}</span>
                          <span>•</span>
                          <span>{item.closed_at ? new Date(item.closed_at).toLocaleTimeString() : 'N/A'}</span>
                        </div>
                      </div>
                      <span className={`font-semibold text-xs px-2 py-0.5 rounded ${isProfit ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-950/50' : 'bg-rose-950/20 text-rose-400 border border-rose-950/50'}`}>
                        {isProfit ? '+' : ''}${pnl.toFixed(2)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>

        {/* SYSTEM EVENT LOGS */}
        <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-900 mb-3">
            <div className="flex items-center gap-2">
              <TerminalSquare size={14} className="text-zinc-500" />
              <span className="font-bold tracking-widest text-zinc-200 uppercase">Live Output logs</span>
            </div>
            <span className="text-[9px] text-zinc-600 font-bold">STREAM ONLINE</span>
          </div>

          <div className="bg-[#070709] border border-zinc-900 rounded-lg p-3 min-h-[120px] max-h-[200px] overflow-y-auto space-y-1.5 font-mono text-[10px] text-zinc-400">
            {activeLogsList.length === 0 ? (
              <div className="text-zinc-700 flex items-center justify-center h-20">
                [ LOADING LIVE BOT EXECUTION STREAM ]
              </div>
            ) : (
              activeLogsList.map((log, index) => {
                let colorClass = "text-zinc-400";
                if (log.message.includes("OPENED")) colorClass = "text-emerald-400 font-semibold";
                else if (log.message.includes("CLOSED")) colorClass = "text-amber-400 font-semibold";
                else if (log.message.includes("Blocked")) colorClass = "text-rose-400/90";
                else if (log.message.includes("GUARD") || log.message.includes("Daily Loss")) colorClass = "text-rose-400 font-semibold";
                else if (log.message.includes("SCANNER")) colorClass = "text-zinc-500";
                else if (log.message.includes("SYSTEM")) colorClass = "text-zinc-500";
                
                return (
                  <div key={index} className="flex gap-4 hover:bg-zinc-900/20 p-0.5 rounded">
                    <span className="text-zinc-600 flex-none">{log.time}</span>
                    <span className={`break-all ${colorClass}`}>{log.message}</span>
                  </div>
                );
              })
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

// Sub-components
function Metric({ title, value, sub, subColor = "text-zinc-600" }: any) {
  return (
    <div className="bg-[#0b0b0e] border border-zinc-900 rounded-xl p-4 flex flex-col justify-between hover:border-zinc-800 transition-colors shadow-lg relative overflow-hidden group">
      <div className="absolute top-0 left-0 right-0 h-[2px] bg-[#8b5cf6] scale-x-0 group-hover:scale-x-100 transition-transform duration-300"></div>
      <span className="text-zinc-500 tracking-widest text-[9px] uppercase font-bold">{title}</span>
      <span className="text-lg text-zinc-100 font-bold font-mono tracking-tight my-2">{value}</span>
      <span className={`text-[10px] font-semibold ${subColor}`}>{sub}</span>
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
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full stroke-[#8b5cf6] fill-transparent stroke-[1.5]">
      <polyline points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ConsoleToggle({ label, description, active, onChange, isGuard = false }: { label: string, description: string, active: boolean, onChange: () => void, isGuard?: boolean }) {
  return (
    <div className="flex items-start justify-between bg-zinc-950/40 border border-zinc-900/60 p-2.5 rounded hover:bg-[#12121a]/10 transition-all select-none">
      <div className="space-y-0.5 max-w-[80%]">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold text-zinc-300 text-[10.5px]">{label}</span>
          {isGuard && (
            <span className="text-[7.5px] px-1 py-0.2 rounded font-extrabold uppercase border border-rose-950/60 bg-rose-950/20 text-rose-400">
              GUARD
            </span>
          )}
        </div>
        <p className="text-[8.5px] text-zinc-600 leading-tight">{description}</p>
      </div>
      <button 
        onClick={onChange}
        className={`w-8 h-4 rounded-full relative p-0.5 transition-colors cursor-pointer ${active ? 'bg-[#8b5cf6]' : 'bg-zinc-800'}`}
      >
        <span className={`h-3 w-3 bg-zinc-100 rounded-full block transition-transform ${active ? 'translate-x-4' : 'translate-x-0'}`}></span>
      </button>
    </div>
  );
}
