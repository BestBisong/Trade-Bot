"use client";

import React, { useState, useEffect } from 'react';
import { 
  Activity, Shield, Cpu, Clock, TerminalSquare, X, Menu,
  Settings, Play, Pause, TrendingUp, TrendingDown, 
  DollarSign, Sliders, Trash2, RefreshCw, AlertTriangle, 
  CheckCircle2, ChevronRight, HelpCircle, ArrowUpRight, ArrowDownRight,
  Info, Eye, History, FileText, Layers, Wallet
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
  'SOL/USDT': { price: 180, vol: 2.5, minQty: 0.01, precision: 2, minNotional: 5.0 },
  'XRP/USDT': { price: 2.45, vol: 0.05, minQty: 1.0, precision: 1, minNotional: 5.0 },
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
  const [activeTab, setActiveTab] = useState<'overview' | 'strategy' | 'diagnostics' | 'logs'>('overview');
  const [modalSymbol, setModalSymbol] = useState<string | null>(null);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [showRiskExplanation, setShowRiskExplanation] = useState(false);
  const [showCostExplanation, setShowCostExplanation] = useState(false);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [activeTab]);
  
  const [apiSaving, setApiSaving] = useState(false);
  const [apiClearSaving, setApiClearSaving] = useState(false);
  const [apiCloseSaving, setApiCloseSaving] = useState<string | null>(null);

  interface Toast {
    id: string;
    message: string;
    type: 'success' | 'error' | 'info';
  }
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4500);
  };
  
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
      symbols: ["BTC/USDT", "SOL/USDT", "XRP/USDT"],
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
      symbols: ["BTC/USDT", "SOL/USDT", "XRP/USDT"],
      trend_guard_enabled: true
    } as BotSettings,
    activeTrades: [] as any[],
    history: [] as any[],
    logs: [
      { time: new Date().toLocaleTimeString(), message: "SYSTEM | Sandbox terminal started. Awaiting virtual market..." }
    ] as any[],
    prices: {
      'BTC/USDT': 92400,
      'SOL/USDT': 180,
      'XRP/USDT': 2.45
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
      'SOL/USDT': {
        regime: 'ranging',
        score: 2.0,
        threshold: 2.5,
        ml_prob: 0.55,
        rsi: 38.5,
        rsi_sig: "BUY",
        sma_sig: "HOLD",
        bb_sig: "BUY",
        market_bullish: false,
        blocked_by: "4H_BEAR_TREND_GUARD"
      },
      'XRP/USDT': {
        regime: 'ranging',
        score: 1.0,
        threshold: 2.5,
        ml_prob: 0.50,
        rsi: 45.2,
        rsi_sig: "HOLD",
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
    'SOL/USDT': generateData(180, 2.5),
    'XRP/USDT': generateData(2.45, 0.05)
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
          'SOL/USDT': prev.prices['SOL/USDT'] + (Math.random() - 0.5) * 1.5,
          'XRP/USDT': prev.prices['XRP/USDT'] + (Math.random() - 0.5) * 0.02
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

            const regime = Math.random() > 0.85 ? 'trending' : 'ranging';
            const market_bullish = Math.random() > 0.6;
            const ml_prob = 0.42 + Math.random() * 0.16;
            const rsi = 30 + Math.random() * 40;
            
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

            const ml_long_threshold = regime === 'ranging' ? 0.55 : 0.58;
            if (ml_prob >= ml_long_threshold) score += 2.0;
            else if (ml_prob <= 0.45) score -= 2.0;

            const threshold = regime === 'ranging' ? 2.5 : 3.0;
            let signal = "HOLD";
            if (score >= threshold) signal = "BUY";
            else if (score <= -threshold) signal = "SELL";

            let blockedReason = null;

            if (signal === "BUY") {
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

            if (signal !== "HOLD" && !blockedReason) {
              const entry_price = newPrices[symbol as keyof typeof newPrices];
              const qty = currentSettings.max_notional_per_trade / entry_price;
              const sl_dist = entry_price * 0.05;
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
              if (Math.random() > 0.4) {
                newLogs.unshift({
                  time: new Date().toLocaleTimeString(),
                  message: `GUARD | ${symbol} ${signal} Signal generated but blocked by ${blockedReason}`
                });
              }
            }
          });
        }

        for (let i = newActiveTrades.length - 1; i >= 0; i--) {
          const trade = newActiveTrades[i];
          const curPrice = newPrices[trade.symbol as keyof typeof newPrices];
          trade.current_price = curPrice;

          const isBuy = trade.side === "buy";
          const pnlVal = isBuy ? (curPrice - trade.entry_price) * trade.qty : (trade.entry_price - curPrice) * trade.qty;
          
          const hitTP = isBuy ? curPrice >= trade.tp : curPrice <= trade.tp;
          const hitSL = isBuy ? curPrice <= trade.sl : curPrice >= trade.sl;

          if (currentSettings.partial_tp_enabled && !trade.has_scaled_out) {
            const hitHalfTP = isBuy ? curPrice >= trade.half_tp : curPrice <= trade.half_tp;
            if (hitHalfTP) {
              const realizedPnl = (isBuy ? (trade.half_tp - trade.entry_price) : (trade.entry_price - trade.half_tp)) * (trade.qty * 0.5);
              newWallet += realizedPnl;
              trade.qty = trade.qty * 0.5;
              trade.sl = trade.entry_price;
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
  const [localSettings, setLocalSettings] = useState<BotSettings | null>(null);

  useEffect(() => {
    if (activeSettings && !localSettings) {
      setLocalSettings(activeSettings);
    }
  }, [activeSettings, localSettings]);

  const displayedSettings = localSettings || activeSettings;
  const hasUnsavedChanges = !!(localSettings && JSON.stringify(localSettings) !== JSON.stringify(activeSettings));
  const activePrices = backendOnline ? systemState.prices : sandboxState.prices;
  const activeDiagnostics = backendOnline ? systemState.diagnostics : sandboxState.diagnostics;
  const activeWallet = backendOnline ? systemState.wallet : sandboxState.wallet;
  const activeTradesList = backendOnline ? activeTrades : sandboxState.activeTrades;
  const activeHistoryList = backendOnline ? history : sandboxState.history;
  const activeLogsList = backendOnline ? logs : sandboxState.logs;

  const checkNoTradeDiagnostics = () => {
    const activeSymbols = activeSettings.symbols || ["BTC/USDT", "SOL/USDT", "XRP/USDT"];
    const now = new Date();
    const twentyFourHoursAgo = now.getTime() - 24 * 60 * 60 * 1000;
    
    return activeSymbols.map(symbol => {
      const tradesForSymbol = activeHistoryList.filter(h => h.symbol === symbol);
      
      let lastTradeTime: Date | null = null;
      if (tradesForSymbol.length > 0 && tradesForSymbol[0].closed_at) {
        lastTradeTime = new Date(tradesForSymbol[0].closed_at);
      }
      
      const noTradeFor24h = !lastTradeTime || lastTradeTime.getTime() < twentyFourHoursAgo;
      
      let statusMessage = "";
      let hoursSince = 0;
      
      if (lastTradeTime) {
        hoursSince = Math.round((now.getTime() - lastTradeTime.getTime()) / (1000 * 60 * 60));
        statusMessage = `Last trade was ${hoursSince} hours ago.`;
      } else {
        statusMessage = "No trade recorded in the current session history.";
      }
      
      let reason = "Scanning indicators for confluence...";
      const diag = activeDiagnostics?.[symbol];
      if (diag) {
        const { blocked_by } = diag;
        if (blocked_by) {
          if (blocked_by === "DAILY_200SMA_GUARD") {
            reason = "Blocked by Daily 200 SMA Guard: Price trend is opposite of authorized trading bias.";
          } else if (blocked_by === "4H_BEAR_TREND_GUARD" || blocked_by === "4H_BULL_TREND_GUARD") {
            reason = "Blocked by 4H Trend Guard: Entry filtered out to align only with macro 4H momentum.";
          } else if (blocked_by === "INSUFFICIENT_SCORE") {
            reason = `Insufficient signal score (${diag.score}/${diag.threshold}): Market is currently too choppy or indicators have not reached a high-probability alignment.`;
          } else if (blocked_by === "SHORTS_DISABLED") {
            reason = "Shorting is disabled in settings. The bot had a sell signal, but was restricted.";
          } else if (blocked_by === "POSITION_ALREADY_OPEN") {
            reason = "An active trade is already open for this asset, preventing new entries.";
          } else if (blocked_by === "SHORTS_RESTRICTED_TO_BTC") {
            reason = "Short positions are restricted to BTC/USDT to protect capital from high altcoin volatility.";
          } else {
            reason = `Blocked by filter: ${blocked_by.replace(/_/g, " ")}.`;
          }
        }
      }
      
      return {
        symbol,
        noTradeFor24h,
        statusMessage,
        reason,
        hoursSince
      };
    });
  };

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
          showToast("Strategy settings saved successfully", "success");
        } else {
          showToast("Failed to save strategy settings", "error");
        }
      } catch (e) {
        console.error("Failed to save settings to API: ", e);
        showToast("Network error: Failed to reach trading engine", "error");
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
      showToast("Sandbox settings updated", "info");
    }
  };

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
          const tradesRes = await fetch(`${apiBase}/api/trades`);
          if (tradesRes.ok) {
            setActiveTrades(await tradesRes.json());
          }
          showToast(`Manual close command executed for ${symbol}`, "success");
        } else {
          showToast(`Failed to close position for ${symbol}`, "error");
        }
      } catch (e) {
        console.error("Failed to close position via API: ", e);
        showToast("Network error: Failed to close position", "error");
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
      showToast(`Sandbox: Closed position for ${symbol}`, "success");
    }
  };

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
          showToast("Trade history cleared successfully", "success");
        } else {
          showToast("Failed to clear trade history", "error");
        }
      } catch (e) {
        console.error("Failed to clear history via API: ", e);
        showToast("Network error: Failed to clear history", "error");
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
      showToast("Sandbox trade history cleared", "success");
    }
  };

  const toggleSetting = (key: keyof BotSettings) => {
    if (!displayedSettings) return;
    const nextSettings = {
      ...displayedSettings,
      [key]: !displayedSettings[key]
    };
    setLocalSettings(nextSettings);
  };

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!displayedSettings) return;
    const val = parseFloat(e.target.value);
    const nextSettings = {
      ...displayedSettings,
      risk_per_trade: val / 100
    };
    setLocalSettings(nextSettings);
  };

  const handleNotionalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!displayedSettings) return;
    const val = parseFloat(e.target.value) || 1.0;
    const nextSettings = {
      ...displayedSettings,
      max_notional_per_trade: val
    };
    setLocalSettings(nextSettings);
  };

  if (!mounted) return null;

  const getAdvisoryMessage = (symbol: string, diag: any) => {
    if (!diag) return { type: 'info', text: "Scanning market data for trade signals..." };
    const { blocked_by, regime, score, threshold } = diag;
    
    if (!activeSettings.auto_trading_enabled) {
      return { type: 'info', text: "The auto-trading scanner is paused. Toggle it ON in the console to allow automatic scans." };
    }
    
    if (blocked_by === "DAILY_200SMA_GUARD") {
      return { type: 'warning', text: `BLOCKED BY DAILY 200 SMA: The price is currently in a macro downtrend. To authorize trades in a bear market, disable the "Daily 200 SMA Guard" in the Strategy Console.` };
    }
    if (blocked_by === "4H_BEAR_TREND_GUARD" || blocked_by === "4H_BULL_TREND_GUARD") {
      return { type: 'warning', text: `BLOCKED BY 4H TREND GUARD: Trend filters are restricting trades against the 4H bias. Disable the "4H Trend Guard" in the Console to authorize entries in choppy/ranging markets.` };
    }
    if (blocked_by === "INSUFFICIENT_SCORE") {
      return { type: 'info', text: `INSUFFICIENT SCORE: Signals do not fully align. Score is ${score} (Threshold is ${threshold}). In sideways markets, consider turning off trend filters or lowering ML constraints to increase scan sensitivity.` };
    }
    if (blocked_by === "SHORTS_DISABLED" && diag.sma_sig === "SELL") {
      return { type: 'info', text: `SELL SIGNAL DETECTED: The bot wants to open a SHORT position, but shorts are disabled. Enable "Allow Short Positions" in the Strategy Console.` };
    }
    if (blocked_by === "POSITION_ALREADY_OPEN") {
      return { type: 'success', text: `POSITION OPEN: An active position is already running for this symbol. Waiting for TP/SL exit before scanning new entries.` };
    }
    if (blocked_by === "MAX_POSITIONS_REACHED") {
      return { type: 'warning', text: `RISK SHIELD: Maximum position limit reached. Close an active trade manually or wait for execution before scanning new entries.` };
    }
    return { type: 'success', text: `SCAN ACTIVE: Auto-trading scanner is running. Price regime is "${regime.toUpperCase()}" with score ${score}/${threshold}.` };
  };

  return (
    <div className="min-h-screen bg-black text-zinc-400 font-sans flex flex-col md:flex-row selection:bg-zinc-800 text-sm antialiased relative">
      
      {/* TOAST NOTIFICATION CORNER */}
      <div className="fixed top-6 right-6 z-50 flex flex-col gap-3 max-w-sm pointer-events-none">
        {toasts.map(t => (
          <div 
            key={t.id}
            className={`
              pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border bg-[#09090b] shadow-2xl text-[10px] font-mono uppercase tracking-wider
              animate-in slide-in-from-top-4 duration-300
              ${t.type === 'success' ? 'border-white text-white' : ''}
              ${t.type === 'error' ? 'border-zinc-800 text-zinc-550' : ''}
              ${t.type === 'info' ? 'border-zinc-950 text-zinc-400' : ''}
            `}
          >
            {t.type === 'success' && <CheckCircle2 size={12} className="text-white flex-shrink-0" />}
            {t.type === 'error' && <AlertTriangle size={12} className="text-zinc-555 flex-shrink-0" />}
            {t.type === 'info' && <Info size={12} className="text-zinc-500 flex-shrink-0" />}
            <span>{t.message}</span>
            <button 
              onClick={() => setToasts(prev => prev.filter(item => item.id !== t.id))}
              className="ml-auto text-zinc-500 hover:text-white p-0.5 focus:outline-none"
            >
              <X size={10} />
            </button>
          </div>
        ))}
      </div>

      {/* MOBILE OVERLAY BACKDROP */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 md:hidden animate-in fade-in duration-200"
          onClick={() => setIsMobileMenuOpen(false)}
        ></div>
      )}

      {/* SIDEBAR NAVIGATION */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-[#09090b] border-r border-zinc-900 flex flex-col justify-between shrink-0 transform 
        md:translate-x-0 md:static md:flex 
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'} 
        transition-transform duration-250 ease-in-out h-full md:h-auto
      `}>
        <div className="p-6">
          {/* LOGO */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <span className="text-white font-bold tracking-widest text-base block font-mono">JARVIS</span>
              <span className="text-[10px] text-zinc-500 font-semibold tracking-wider font-mono">QUANT WORKSTATION</span>
            </div>
            {/* Close button visible only on mobile/tablet inside sidebar */}
            <button 
              onClick={() => setIsMobileMenuOpen(false)}
              className="md:hidden text-zinc-400 hover:text-white p-1 focus:outline-none"
            >
              <X size={18} />
            </button>
          </div>

          {/* MENU LINKS */}
          <nav className="space-y-1">
            <button
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group text-left ${activeTab === 'overview' ? 'bg-white text-black font-semibold' : 'hover:bg-zinc-900 text-zinc-400 hover:text-white'}`}
            >
              <Activity size={16} className={activeTab === 'overview' ? 'text-black' : 'text-zinc-500 group-hover:text-white'} />
              <span className="text-xs uppercase tracking-wider font-medium">Overview</span>
            </button>
            <button
              onClick={() => setActiveTab('strategy')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group text-left ${activeTab === 'strategy' ? 'bg-white text-black font-semibold' : 'hover:bg-zinc-900 text-zinc-400 hover:text-white'}`}
            >
              <Sliders size={16} className={activeTab === 'strategy' ? 'text-black' : 'text-zinc-500 group-hover:text-white'} />
              <span className="text-xs uppercase tracking-wider font-medium">Strategy & Console</span>
            </button>
            <button
              onClick={() => setActiveTab('diagnostics')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group text-left ${activeTab === 'diagnostics' ? 'bg-white text-black font-semibold' : 'hover:bg-zinc-900 text-zinc-400 hover:text-white'}`}
            >
              <Shield size={16} className={activeTab === 'diagnostics' ? 'text-black' : 'text-zinc-500 group-hover:text-white'} />
              <span className="text-xs uppercase tracking-wider font-medium">Inactivity Monitor</span>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl transition-all duration-200 group text-left ${activeTab === 'logs' ? 'bg-white text-black font-semibold' : 'hover:bg-zinc-900 text-zinc-400 hover:text-white'}`}
            >
              <TerminalSquare size={16} className={activeTab === 'logs' ? 'text-black' : 'text-zinc-500 group-hover:text-white'} />
              <span className="text-xs uppercase tracking-wider font-medium">Logs & History</span>
            </button>
          </nav>
        </div>

        {/* FOOTER STATE BADGE */}
        <div className="p-6 border-t border-zinc-900/60 space-y-4">
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${backendOnline ? 'bg-white animate-pulse' : 'bg-transparent border border-zinc-650'}`}></span>
            <span className="text-[11px] font-mono font-semibold tracking-widest text-zinc-300">
              {backendOnline ? 'Terminal: CONNECTED' : 'Terminal: SANDBOX'}
            </span>
          </div>

        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 min-w-0 flex flex-col bg-black">
        
        {/* HEADER BAR */}
        <header className="h-auto md:h-16 border-b border-zinc-900 bg-[#09090b] px-6 md:px-8 py-4 md:py-0 flex flex-col md:flex-row md:items-center justify-between gap-4 md:gap-0">
          <div className="flex items-center justify-between w-full md:w-auto">
            <span className="text-xs uppercase tracking-widest font-semibold text-zinc-500 font-mono">
              Dashboard / {activeTab}
            </span>
            {/* Mobile hamburger menu toggle */}
            <button 
              onClick={() => setIsMobileMenuOpen(true)}
              className="md:hidden text-zinc-400 hover:text-white p-1 focus:outline-none"
            >
              <Menu size={20} />
            </button>
          </div>

          {/* CAPITAL HUD */}
          <div className="flex flex-wrap items-center gap-4 md:gap-6 w-full md:w-auto text-xs justify-between md:justify-end">
            <div className="flex items-center gap-2">
              <Wallet size={14} className="text-zinc-500" />
              <span className="text-zinc-400 font-semibold uppercase tracking-wider">WALLET:</span>
              <span className="text-white font-bold font-mono">
                ${activeWallet.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
            {backendOnline && (
              <div className="flex items-center gap-2 border-l border-zinc-900 pl-6">
                <TrendingUp size={14} className="text-zinc-555" />
                <span className="text-zinc-400 font-semibold uppercase tracking-wider">PnL Today:</span>
                <span className={`font-mono font-bold ${systemState.risk.daily_pnl_pct >= 0 ? 'text-white' : 'text-zinc-500'}`}>
                  {systemState.risk.daily_pnl_pct >= 0 ? '+' : ''}{systemState.risk.daily_pnl_pct.toFixed(2)}%
                </span>
              </div>
            )}
            <div className="flex items-center gap-2 border-l border-zinc-900 pl-6 text-zinc-500">
              <Clock size={14} />
              <span className="font-mono text-[11px]">{new Date().toISOString().split('T')[1].split('.')[0]} UTC</span>
            </div>
          </div>
        </header>

        {/* CONTENT VIEW PORT */}
        <div className="flex-1 p-4 md:p-8 overflow-y-auto max-w-[1500px]">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-8">
              
              {/* HEADING AND METRICS */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight uppercase">Market Overview</h2>
                  <p className="text-xs text-zinc-500 mt-1 uppercase tracking-wider">Click any scanner card to inspect technical indicators and guards</p>
                </div>

                <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                  <span className="text-xs bg-zinc-900 text-zinc-400 px-3 py-1.5 rounded-full border border-zinc-800 font-semibold font-mono">
                    ACTIVE POSITIONS: {activeTradesList.length}
                  </span>
                  <span className="text-xs bg-zinc-900 text-zinc-400 px-3 py-1.5 rounded-full border border-zinc-800 font-semibold font-mono">
                    WIN RATE: {backendOnline ? `${systemState.risk.win_rate.toFixed(1)}%` : `${activeHistoryList.length > 0 ? ((activeHistoryList.filter(h => h.pnl > 0).length / activeHistoryList.length) * 100).toFixed(1) : '0.0'}%`}
                  </span>
                </div>
              </div>

              {/* LIVE SCANNER CARDS */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {Object.keys(COIN_CONFIGS).map((symbol) => {
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
                      onClick={() => setModalSymbol(symbol)}
                      className="bg-[#09090b] border border-zinc-900 rounded-2xl p-6 flex flex-col justify-between transition-all duration-200 hover:border-white hover:bg-zinc-950/60 cursor-pointer select-none relative group h-48 shadow-sm"
                    >
                      <div>
                        {/* Title and live price */}
                        <div className="flex justify-between items-start">
                          <div>
                            <span className="text-white font-bold text-base tracking-wider block font-mono">{symbol}</span>
                            <span className="text-[10px] font-mono mt-1 inline-flex items-center gap-1.5 text-zinc-400 uppercase tracking-widest font-semibold">
                              <span className="h-1 w-1 rounded-full bg-zinc-400"></span>
                              {regime} regime
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-[9px] text-zinc-500 block font-mono tracking-widest uppercase">PRICE</span>
                            <span className="text-lg text-white font-semibold font-mono tracking-tight">
                              ${livePrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </span>
                          </div>
                        </div>

                        {/* Sparkline visualization */}
                        <div className="h-10 opacity-30 my-4">
                          <Sparkline data={sparklines[symbol as keyof typeof sparklines]} />
                        </div>
                      </div>

                      {/* Diagnostic summary footer */}
                      <div className="pt-3 border-t border-zinc-900 flex justify-between items-center text-xs">
                        <div className="flex items-center gap-2">
                          <span className={`h-2 w-2 rounded-full ${isBlocked ? 'bg-transparent border border-white' : (isOpened ? 'bg-white' : 'bg-zinc-800')}`}></span>
                          <span className="font-mono tracking-wider text-zinc-400 text-[10px]">
                            {isBlocked ? "BLOCKED BY GUARD" : (isOpened ? "ACTIVE POSITION" : "PENDING ALIGNMENT")}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono text-zinc-500 hover:text-white transition-colors flex items-center gap-1 uppercase font-semibold">
                          Inspect <Eye size={12} />
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* ACTIVE RUNNING POSITIONS TABLE */}
              <div className="bg-[#09090b] border border-zinc-900 rounded-2xl p-6 shadow-sm">
                <div className="flex items-center justify-between pb-4 border-b border-zinc-900 mb-6">
                  <div className="flex items-center gap-2">
                    <Shield size={16} className="text-zinc-500" />
                    <h3 className="font-bold text-sm text-zinc-200 tracking-wider uppercase">Active Positions</h3>
                  </div>
                  <span className="text-[10px] text-zinc-500 font-mono font-semibold uppercase bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-full">
                    OPEN TRADES: {activeTradesList.length}
                  </span>
                </div>

                {activeTradesList.length === 0 ? (
                  <div className="flex flex-col items-center justify-center text-zinc-550 text-xs py-16 space-y-2 border border-dashed border-zinc-900 rounded-2xl bg-zinc-950/20">
                    <span className="font-mono text-zinc-550">[ NO ACTIVE POSITIONS ]</span>
                    <span className="text-[10px] text-zinc-600 uppercase tracking-widest text-center max-w-md mt-1">
                      The execution engine is scanning. Trades will auto-enter when confluence signals align.
                    </span>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="text-zinc-500 border-b border-zinc-900 pb-3 font-mono uppercase tracking-wider text-[10px]">
                          <th className="pb-3 font-semibold">Symbol</th>
                          <th className="pb-3 font-semibold">Side</th>
                          <th className="pb-3 font-semibold">Entry Price</th>
                          <th className="pb-3 font-semibold">Current Price</th>
                          <th className="pb-3 font-semibold">Position Size</th>
                          <th className="pb-3 font-semibold">SL / TP Target</th>
                          <th className="pb-3 text-right font-semibold">Unrealized P&L</th>
                          <th className="pb-3 text-right font-semibold">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-900">
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
                            <tr key={index} className="hover:bg-zinc-950/40 transition-colors duration-150">
                              <td className="py-4 font-bold text-white font-mono">{t.symbol}</td>
                              <td className="py-4">
                                <span className={`font-bold font-mono text-[10px] tracking-wider ${t.side === 'buy' ? 'text-white' : 'text-zinc-400'}`}>
                                  {t.side === 'buy' ? 'LONG' : 'SHORT'}
                                </span>
                              </td>
                              <td className="py-4 font-mono">${entry.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</td>
                              <td className="py-4 font-mono text-zinc-500">${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}</td>
                              <td className="py-4 font-mono">
                                <span className="block text-zinc-300">{qty.toFixed(5)}</span>
                                <span className="text-[10px] text-zinc-550">${(qty * entry).toFixed(2)} USDT</span>
                              </td>
                              <td className="py-4 font-mono text-[10px] text-zinc-500 space-y-0.5">
                                <div className="text-zinc-500">SL: ${parseFloat(t.sl).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                                <div className="text-zinc-300">TP: ${parseFloat(t.tp).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                              </td>
                              <td className={`py-4 text-right font-mono font-semibold ${isProfit ? 'text-white' : 'text-zinc-550'}`}>
                                <div className="text-sm">{isProfit ? '+$' : '-$'}{Math.abs(pnlVal).toFixed(2)}</div>
                                <div className="text-[10px]">{isProfit ? '+' : ''}{pnlPct.toFixed(2)}%</div>
                              </td>
                              <td className="py-4 text-right">
                                <button
                                  onClick={() => closePosition(t.symbol)}
                                  disabled={apiCloseSaving === t.symbol}
                                  className="bg-transparent hover:bg-white text-white hover:text-black border border-zinc-800 hover:border-white px-3 py-1.5 rounded-lg transition-all duration-200 cursor-pointer disabled:opacity-50 text-[10px] font-semibold uppercase tracking-wider font-mono"
                                >
                                  {apiCloseSaving === t.symbol ? (
                                    <RefreshCw size={12} className="animate-spin" />
                                  ) : (
                                    "CLOSE"
                                  )}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

            </div>
          )}

          {/* TAB 2: STRATEGY & RULES */}
          {activeTab === 'strategy' && (
            <div className="space-y-8 max-w-4xl">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight uppercase">Strategy Adjustments & Risk Guards</h2>
                <p className="text-xs text-zinc-550 mt-1 uppercase tracking-wider">Fine-tune execution parameters and toggle active machine learning shields</p>
              </div>

              <div className="bg-[#09090b] border border-zinc-900 rounded-2xl p-6 space-y-6">
                
                {/* SETTINGS GRID */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <ConsoleToggle 
                    label="Scanner Auto-Trading" 
                    description="Toggle the automatic market scanner loop"
                    active={displayedSettings.auto_trading_enabled}
                    onChange={() => toggleSetting("auto_trading_enabled")}
                    explanation="Turns on the bot's autopilot scanner. When active, it constantly watches market prices and places trades automatically based on your strategy. Turn it off to stop all automated trades."
                  />
                  
                  <ConsoleToggle 
                    label="Daily 200 SMA Guard" 
                    description="Restricts buys below daily 200 SMA (Bear Protection)"
                    active={displayedSettings.daily_200sma_guard}
                    onChange={() => toggleSetting("daily_200sma_guard")}
                    isGuard={true}
                    explanation="A safety net that only allows buying when the market is in a long-term uptrend (healthy market). It protects your money by blocking buy orders when the overall market is in a long-term downturn."
                  />

                  <ConsoleToggle 
                    label="4H Trend Guard" 
                    description="Restricts counter-trend entries based on 4H MACD"
                    active={displayedSettings.trend_guard_enabled}
                    onChange={() => toggleSetting("trend_guard_enabled")}
                    isGuard={true}
                    explanation="Keeps the bot aligned with the medium-term market direction (over the last 4 hours). It stops the bot from buying when the price is currently falling, avoiding catching a falling knife."
                  />

                  <ConsoleToggle 
                    label="Allow Short Positions" 
                    description="Allows opening short positions in bearish trends"
                    active={displayedSettings.allow_shorts}
                    onChange={() => toggleSetting("allow_shorts")}
                    explanation="Allows the bot to make money when prices are going down. When turned on, the bot can enter a short trade (betting the price will drop) to profit from downward trends."
                  />

                  <ConsoleToggle 
                    label="Trailing ATR Stop Loss" 
                    description="Dynamically raises stop loss using 3x rolling ATR"
                    active={displayedSettings.trailing_stop_enabled}
                    onChange={() => toggleSetting("trailing_stop_enabled")}
                    explanation="A smart exit guard that locks in profits automatically. As the price goes up, the bot drags its safety line (Stop Loss) up behind it. If the price suddenly reverses, it exits early with the profit you already made."
                  />

                  <ConsoleToggle 
                    label="Partial Profit Scale-out" 
                    description="Locks 50% profit at 1:1 RR and moves SL to breakeven"
                    active={displayedSettings.partial_tp_enabled}
                    onChange={() => toggleSetting("partial_tp_enabled")}
                    explanation="Automatically locks in partial profits. When a trade is halfway to its target, it sells 50% of the coin to secure that gain and moves the remaining safety line to your entry price, ensuring you cannot lose on the rest."
                  />

                  <ConsoleToggle 
                    label="Dynamic ML Risk Sizing" 
                    description="Sizes risk (3% - 6.5%) based on brain confidence"
                    active={displayedSettings.dynamic_ml_risk}
                    onChange={() => toggleSetting("dynamic_ml_risk")}
                    explanation="Allows the AI brain to adjust trade size. If the AI is highly confident about a trade, it will risk slightly more capital (up to 6.5%). If confidence is low, it risks less (minimum 3%) to protect your account."
                  />
                </div>

                {/* NUMERIC PARAMETERS */}
                <div className="pt-6 border-t border-zinc-900 grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div>
                    <div className="flex justify-between text-xs mb-2 font-mono uppercase items-center">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-400">Risk Allocation Per Trade</span>
                        <button 
                          onClick={() => setShowRiskExplanation(!showRiskExplanation)}
                          className={`text-zinc-550 hover:text-white transition-colors focus:outline-none p-0.5 rounded-full hover:bg-zinc-900 ${showRiskExplanation ? 'text-white' : ''}`}
                          title="Explain risk allocation in simple terms"
                        >
                          <Info size={12} />
                        </button>
                      </div>
                      <span className="text-white font-semibold">{(displayedSettings.risk_per_trade * 100).toFixed(1)}%</span>
                    </div>
                    <input 
                      type="range" 
                      min="1.0" 
                      max="10.0" 
                      step="0.5"
                      value={displayedSettings.risk_per_trade * 100}
                      onChange={handleSliderChange}
                      className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-white"
                    />
                    {showRiskExplanation ? (
                      <div className="mt-2 text-[10px] text-zinc-450 leading-relaxed bg-black/40 border border-zinc-900 p-2.5 rounded-lg font-mono uppercase tracking-wider animate-in fade-in slide-in-from-top-1 duration-150">
                        <span className="text-white font-bold block mb-1">Simple Explanation:</span>
                        How much of your account balance you are willing to risk on a single bad trade. If set to 5%, a worst-case trade that hits the safety exit (Stop Loss) will only lose 5% of your total balance.
                      </div>
                    ) : (
                      <span className="text-[10px] text-zinc-550 block mt-2 uppercase tracking-wider leading-relaxed">
                        Defines the mathematical capital allocation exposed per Stop Loss distance.
                      </span>
                    )}
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-2 font-mono uppercase items-center">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-400">Max Trade Cost Limit</span>
                        <button 
                          onClick={() => setShowCostExplanation(!showCostExplanation)}
                          className={`text-zinc-550 hover:text-white transition-colors focus:outline-none p-0.5 rounded-full hover:bg-zinc-900 ${showCostExplanation ? 'text-white' : ''}`}
                          title="Explain cost limit in simple terms"
                        >
                          <Info size={12} />
                        </button>
                      </div>
                      <span className="text-white font-semibold">${displayedSettings.max_notional_per_trade.toFixed(2)} USDT</span>
                    </div>
                    <div className="relative flex items-center">
                      <span className="absolute left-3 text-zinc-550 font-mono">$</span>
                      <input 
                        type="number" 
                        min="1.0" 
                        max="10.0" 
                        value={displayedSettings.max_notional_per_trade}
                        onChange={handleNotionalChange}
                        className="w-full bg-zinc-950 border border-zinc-900 rounded-xl px-8 py-2.5 focus:border-white focus:outline-none text-white text-xs font-mono"
                      />
                    </div>
                    {showCostExplanation ? (
                      <div className="mt-2 text-[10px] text-zinc-450 leading-relaxed bg-black/40 border border-zinc-900 p-2.5 rounded-lg font-mono uppercase tracking-wider animate-in fade-in slide-in-from-top-1 duration-150">
                        <span className="text-white font-bold block mb-1">Simple Explanation:</span>
                        The maximum dollar amount (in USDT) the bot is allowed to put into any single trade. It acts as an absolute spending limit per trade, regardless of the risk setting.
                      </div>
                    ) : (
                      <span className="text-[10px] text-zinc-555 block mt-2 uppercase tracking-wider leading-relaxed">
                        Absolute maximum capital allocated per position entry.
                      </span>
                    )}
                  </div>
                </div>

                {/* ACTION BUTTON */}
                <div className="space-y-3 pt-4 border-t border-zinc-900">
                  {hasUnsavedChanges && (
                    <div className="flex items-center gap-2 text-[10px] text-white font-mono uppercase tracking-wider bg-zinc-900 border border-zinc-800 px-4 py-2.5 rounded-xl animate-pulse">
                      <AlertTriangle size={12} className="text-white shrink-0" />
                      <span>Unsaved Changes Detected • Pending Bot Push</span>
                    </div>
                  )}
                  <button 
                    onClick={() => saveSettings(displayedSettings)}
                    disabled={apiSaving}
                    className={`w-full font-semibold py-3 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 text-xs shadow-sm uppercase font-mono tracking-wider ${hasUnsavedChanges ? 'bg-white text-black hover:bg-zinc-200' : 'bg-zinc-900 text-zinc-450 border border-zinc-850 hover:text-white hover:border-zinc-700'}`}
                  >
                    {apiSaving ? (
                      <>
                        <RefreshCw size={14} className="animate-spin" /> Saving Settings...
                      </>
                    ) : (
                      backendOnline ? "Save Configuration to Bot Engine" : "Save Configuration to Sandbox"
                    )}
                  </button>
                </div>

              </div>
            </div>
          )}

          {/* TAB 3: INACTIVITY DIAGNOSTICS */}
          {activeTab === 'diagnostics' && (
            <div className="space-y-8 max-w-4xl">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight uppercase">System Inactivity Monitor</h2>
                <p className="text-xs text-zinc-550 mt-1 uppercase tracking-wider">Tracks inactive intervals and diagnoses exactly why positions have not been entered</p>
              </div>

              <div className="bg-[#09090b] border border-zinc-900 rounded-2xl p-6 space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-zinc-900">
                  <AlertTriangle size={16} className="text-zinc-500" />
                  <span className="font-semibold text-xs text-zinc-400 tracking-wider uppercase font-mono">24H Scan Activity Status</span>
                </div>
                
                <div className="divide-y divide-zinc-900">
                  {checkNoTradeDiagnostics().map(({ symbol, noTradeFor24h, statusMessage, reason }) => (
                    <div key={symbol} className="py-5 first:pt-0 last:pb-0 space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-white font-mono text-sm tracking-wider">{symbol}</span>
                        <span className={`text-[9px] font-mono font-semibold px-2.5 py-0.5 rounded-full border uppercase ${
                          noTradeFor24h ? "border-white bg-transparent text-white" : "border-zinc-800 bg-transparent text-zinc-600"
                        }`}>
                          {noTradeFor24h ? "24h+ inactive" : "active interval"}
                        </span>
                      </div>
                      
                      <div className="text-xs text-zinc-450 flex items-center gap-2">
                        <Clock size={12} className="text-zinc-550" />
                        <span>{statusMessage}</span>
                      </div>
                      
                      <div className="p-4 rounded-xl border bg-zinc-950/40 border-zinc-900 text-xs text-zinc-450 leading-relaxed">
                        <span className="text-zinc-500 font-bold uppercase tracking-wider mr-1 font-mono">Diagnosis:</span>
                        {reason}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: LOGS & COMPLETED HISTORY */}
          {activeTab === 'logs' && (
            <div className="space-y-8">
              
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight uppercase">Logs & Executions History</h2>
                  <p className="text-xs text-zinc-550 mt-1 uppercase tracking-wider">Inspect output stream and review recent trade terminations</p>
                </div>
                
                {activeHistoryList.length > 0 && (
                  <button
                    onClick={clearHistory}
                    disabled={apiClearSaving}
                    className="text-zinc-500 hover:text-white flex items-center gap-2 transition-colors cursor-pointer text-xs font-semibold uppercase font-mono tracking-wider bg-zinc-900 border border-zinc-800 px-4 py-2 rounded-xl hover:bg-zinc-950"
                  >
                    <Trash2 size={12} /> Clear History
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* EVENT LOGS STREAM (2/3 width) */}
                <div className="lg:col-span-2 bg-[#09090b] border border-zinc-900 rounded-2xl p-6 space-y-4 flex flex-col h-[520px]">
                  <div className="flex items-center justify-between pb-3 border-b border-zinc-900/60">
                    <div className="flex items-center gap-2">
                      <TerminalSquare size={16} className="text-zinc-500" />
                      <span className="font-semibold text-xs text-zinc-400 tracking-wider uppercase font-mono">Execution Stream Output</span>
                    </div>
                    <span className="text-[10px] text-zinc-500 font-mono font-semibold uppercase bg-zinc-950 border border-zinc-900 px-2 py-0.5 rounded-full">
                      Real-time
                    </span>
                  </div>

                  <div className="flex-1 bg-black border border-zinc-900 rounded-xl p-4 overflow-y-auto space-y-2 font-mono text-xs text-zinc-400">
                    {activeLogsList.length === 0 ? (
                      <div className="text-zinc-650 flex items-center justify-center h-full uppercase font-mono">
                        [ WAITING FOR SYSTEM LOG BUFFER ]
                      </div>
                    ) : (
                      activeLogsList.map((log, index) => {
                        let colorClass = "text-zinc-400";
                        if (log.message.includes("OPENED") || log.message.includes("CLOSED")) colorClass = "text-white font-semibold";
                        else if (log.message.includes("Blocked") || log.message.includes("GUARD") || log.message.includes("Daily Loss")) colorClass = "text-zinc-300 font-medium";
                        else if (log.message.includes("SCANNER") || log.message.includes("SYSTEM")) colorClass = "text-zinc-600";
                        
                        return (
                          <div key={index} className="flex gap-4 hover:bg-zinc-900/30 p-1.5 rounded transition-colors">
                            <span className="text-zinc-600 flex-none select-none">{log.time}</span>
                            <span className={`break-all ${colorClass}`}>{log.message}</span>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* COMPLETED HISTORY SIDEBAR (1/3 width) */}
                <div className="bg-[#09090b] border border-zinc-900 rounded-2xl p-6 space-y-4 flex flex-col h-[520px]">
                  <div className="flex items-center gap-2 pb-3 border-b border-zinc-900">
                    <History size={16} className="text-zinc-500" />
                    <span className="font-semibold text-xs text-zinc-400 tracking-wider uppercase font-mono">Completed Trades</span>
                  </div>

                  {activeHistoryList.length === 0 ? (
                    <div className="flex-1 flex items-center justify-center text-zinc-600 text-xs font-mono uppercase text-center p-4">
                      [ NO COMPLETED TRADES REGISTERED ]
                    </div>
                  ) : (
                    <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
                      {activeHistoryList.map((item, idx) => {
                        const pnl = parseFloat(item.pnl) || 0;
                        const isProfit = pnl >= 0;
                        return (
                          <div key={idx} className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 flex justify-between items-center text-xs hover:border-zinc-800 transition-colors">
                            <div>
                              <span className="font-bold text-white font-mono tracking-wider">{item.symbol}</span>
                              <div className="flex items-center gap-2 text-zinc-500 text-[10px] mt-1.5 uppercase font-mono">
                                <span>{item.reason}</span>
                                <span>•</span>
                                <span className="font-mono text-[9px]">{item.closed_at ? new Date(item.closed_at).toLocaleTimeString() : 'N/A'}</span>
                              </div>
                            </div>
                            <span className={`font-mono text-xs px-2.5 py-0.5 rounded-full border ${isProfit ? 'border-white text-white font-semibold' : 'border-zinc-800 text-zinc-550'}`}>
                              {isProfit ? '+$' : '-$'}{Math.abs(pnl).toFixed(2)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

              </div>
            </div>
          )}

        </div>
      </main>

      {/* TABS INTERACTIVE DIAGNOSTICS MODAL OVERLAY */}
      {modalSymbol && (() => {
        const symbol = modalSymbol;
        const livePrice = activePrices?.[symbol] || COIN_CONFIGS[symbol].price;
        const diag = activeDiagnostics?.[symbol];
        const regime = diag?.regime || "ranging";
        const score = diag?.score || 0.0;
        const threshold = diag?.threshold || 2.5;
        const mlConf = diag?.ml_prob ? (diag.ml_prob * 100).toFixed(1) : "50.0";
        const rsi = diag?.rsi ? diag.rsi.toFixed(1) : "50.0";
        const advisory = getAdvisoryMessage(symbol, diag);

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
            <div className="bg-[#09090b] border border-zinc-900 rounded-2xl max-w-lg w-full p-6 relative space-y-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
              
              {/* Header */}
              <div className="flex justify-between items-start pb-4 border-b border-zinc-900">
                <div>
                  <h3 className="text-lg font-bold text-white font-mono tracking-wider">{symbol} DIAGNOSTICS</h3>
                  <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest font-semibold block mt-0.5">TECHNICAL ALIGNMENT DETAILS</span>
                </div>
                <button 
                  onClick={() => setModalSymbol(null)}
                  className="text-zinc-500 hover:text-white border border-zinc-900 hover:border-zinc-800 p-1.5 rounded-xl transition-all cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-3">
                  <span className="text-zinc-500 block text-[9px] uppercase tracking-wider font-mono">REGIME</span>
                  <span className="text-white font-bold font-mono tracking-wide uppercase text-sm mt-0.5">{regime}</span>
                </div>
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-3">
                  <span className="text-zinc-500 block text-[9px] uppercase tracking-wider font-mono">VERDICT SCORE</span>
                  <span className="text-white font-bold font-mono tracking-wide text-sm mt-0.5">{score} / {threshold}</span>
                </div>
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-3">
                  <span className="text-zinc-500 block text-[9px] uppercase tracking-wider font-mono">ML BRAIN PROBABILITY</span>
                  <span className="text-white font-bold font-mono tracking-wide text-sm mt-0.5">{mlConf}%</span>
                </div>
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-3">
                  <span className="text-zinc-500 block text-[9px] uppercase tracking-wider font-mono">LIVE VALUE</span>
                  <span className="text-white font-bold font-mono tracking-wide text-sm mt-0.5">${livePrice.toLocaleString()}</span>
                </div>
              </div>

              {/* Technical Indicator Indicators */}
              <div className="bg-zinc-950/30 p-4 rounded-xl border border-zinc-900 space-y-3.5">
                <span className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest font-semibold block">CONFLUENCE MATRICES</span>
                
                <div className="grid grid-cols-3 gap-2.5 text-center text-xs">
                  <div className="border border-zinc-900 p-2.5 rounded-lg bg-zinc-950/60">
                    <span className="text-zinc-500 block text-[9px] uppercase tracking-wider mb-1 font-mono">RSI ({rsi})</span>
                    <span className={`font-semibold font-mono text-[10px] ${diag?.rsi_sig === "BUY" ? "text-white" : (diag?.rsi_sig === "SELL" ? "text-zinc-400" : "text-zinc-600")}`}>
                      {diag?.rsi_sig || "HOLD"}
                    </span>
                  </div>
                  <div className="border border-zinc-900 p-2.5 rounded-lg bg-zinc-950/60">
                    <span className="text-zinc-500 block text-[9px] uppercase tracking-wider mb-1 font-mono">BOLLINGER</span>
                    <span className={`font-semibold font-mono text-[10px] ${diag?.bb_sig === "BUY" ? "text-white" : (diag?.bb_sig === "SELL" ? "text-zinc-400" : "text-zinc-600")}`}>
                      {diag?.bb_sig || "HOLD"}
                    </span>
                  </div>
                  <div className="border border-zinc-900 p-2.5 rounded-lg bg-zinc-950/60">
                    <span className="text-zinc-500 block text-[9px] uppercase tracking-wider mb-1 font-mono">MACD / SMA</span>
                    <span className={`font-semibold font-mono text-[10px] ${diag?.sma_sig === "BUY" ? "text-white" : (diag?.sma_sig === "SELL" ? "text-zinc-400" : "text-zinc-600")}`}>
                      {diag?.sma_sig || "HOLD"}
                    </span>
                  </div>
                </div>

                <div className="flex justify-between items-center text-xs border-t border-zinc-900/60 pt-3">
                  <span className="text-zinc-500 uppercase tracking-widest font-mono text-[9px]">4H MACRO BIAS</span>
                  <span className={`font-bold font-mono text-[10px] ${diag?.market_bullish ? 'text-white' : 'text-zinc-550'}`}>
                    {diag?.market_bullish ? 'BULLISH BIAS' : 'BEARISH BIAS'}
                  </span>
                </div>
              </div>

              {/* Advisory Message */}
              <div className="p-4 rounded-xl flex items-start gap-3 border bg-zinc-950/40 border-zinc-900 text-zinc-400">
                <div className="mt-0.5">
                  {advisory.type === "warning" && <AlertTriangle size={15} className="text-white flex-none" />}
                  {advisory.type === "success" && <CheckCircle2 size={15} className="text-white flex-none" />}
                  {advisory.type === "info" && <Info size={15} className="text-zinc-400 flex-none" />}
                </div>
                <div className="leading-relaxed text-xs">
                  {advisory.text}
                </div>
              </div>

              {/* Footer close button */}
              <button 
                onClick={() => setModalSymbol(null)}
                className="w-full bg-white hover:bg-zinc-200 text-black py-2.5 rounded-xl text-xs font-semibold uppercase font-mono tracking-wider cursor-pointer transition-colors"
              >
                Close View
              </button>

            </div>
          </div>
        );
      })()}

    </div>
  );
}

// Sub-components
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
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full stroke-zinc-500/80 fill-transparent stroke-[1.5]">
      <polyline points={points} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function ConsoleToggle({ label, description, active, onChange, isGuard = false, explanation }: { label: string, description: string, active: boolean, onChange: () => void, isGuard?: boolean, explanation?: string }) {
  const [showExplanation, setShowExplanation] = useState(false);

  return (
    <div className="flex flex-col bg-zinc-900/10 border border-zinc-900 rounded-xl p-3.5 hover:border-zinc-800 transition-all duration-200 select-none gap-2">
      <div className="flex items-start justify-between">
        <div className="space-y-1 max-w-[80%]">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-zinc-200 text-xs tracking-wide uppercase font-mono">{label}</span>
            {isGuard && (
              <span className="text-[8px] px-2 py-0.5 rounded-full font-semibold uppercase bg-zinc-900 text-zinc-400 border border-zinc-800 font-mono">
                GUARD
              </span>
            )}
            {explanation && (
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  setShowExplanation(!showExplanation);
                }}
                className={`text-zinc-550 hover:text-white transition-colors focus:outline-none p-0.5 rounded-full hover:bg-zinc-900 ${showExplanation ? 'text-white' : ''}`}
                title="Explain setting in simple terms"
              >
                <Info size={12} />
              </button>
            )}
          </div>
          <p className="text-[11px] text-zinc-500 leading-normal">{description}</p>
        </div>
        <button 
          onClick={onChange}
          className={`w-9 h-5 rounded-full relative p-0.5 transition-colors duration-200 cursor-pointer shrink-0 ${active ? 'bg-white' : 'bg-zinc-800'}`}
        >
          <span className={`h-4 w-4 rounded-full block transition-transform duration-200 ${active ? 'translate-x-4 bg-zinc-950' : 'translate-x-0 bg-zinc-400'}`}></span>
        </button>
      </div>

      {showExplanation && explanation && (
        <div className="text-[10px] text-zinc-450 leading-relaxed bg-black/40 border border-zinc-900 p-2.5 rounded-lg font-mono uppercase tracking-wider animate-in fade-in slide-in-from-top-1 duration-150">
          <span className="text-white font-bold block mb-1">Simple Explanation:</span>
          {explanation}
        </div>
      )}
    </div>
  );
}
