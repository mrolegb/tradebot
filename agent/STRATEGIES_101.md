# Strategies 101

This file explains the bot strategies in plain language.

## What A Strategy Does

A strategy answers one simple question:

```text
Should we buy, sell, or do nothing right now?
```

In code, every strategy returns a `Signal`:

```text
BUY   = open or prefer a long position
SELL  = open or prefer a short position
HOLD  = do nothing
```

The bot then sends that signal through risk checks. A strategy is not allowed to decide position size by itself.

The strategy files are here:

```text
app/strategies/
```

## The Three Current Strategies

## 1. EMA Cross

File:

```text
app/strategies/ema_cross.py
```

EMA means "exponential moving average". Think of it as a smoothed price line.

This strategy uses two smoothed lines:

```text
fast EMA = reacts quickly
slow EMA = reacts slowly
```

The idea:

```text
fast line crosses above slow line = price may be starting to go up = BUY
fast line crosses below slow line = price may be starting to go down = SELL
no cross = HOLD
```

Simple example:

```text
Yesterday: fast EMA was below slow EMA
Today:     fast EMA is above slow EMA
Signal:   BUY
```

Good for:
- catching a new trend

Bad for:
- sideways/choppy markets, where lines cross back and forth and create bad trades

## 2. RSI Mean Reversion

File:

```text
app/strategies/rsi_mean_reversion.py
```

RSI is a number from 0 to 100.

Roughly:

```text
low RSI  = price may be oversold
high RSI = price may be overbought
```

Default logic:

```text
RSI <= 30 = BUY
RSI >= 70 = SELL
otherwise = HOLD
```

The idea is "price moved too far, maybe it snaps back".

Good for:
- range-bound markets
- markets that bounce up and down

Bad for:
- strong trends, because "overbought" can stay overbought and keep going up
- strong downtrends, because "oversold" can keep falling

## 3. Breakout

File:

```text
app/strategies/breakout.py
```

This is currently the most developed strategy.

A breakout means:

```text
price escapes above a recent high
or
price escapes below a recent low
```

The bot looks back over recent candles, for example 20 candles:

```text
recent high = highest close in the last 20 candles
recent low  = lowest close in the last 20 candles
```

Then it adds a small buffer, so it does not buy just because price barely touched the level.

Example:

```text
recent high = 100
buffer      = 0.12%
buy level   = 100.12

if price closes above 100.12, breakout may be real
```

But the strategy does not buy immediately. It also checks filters.

## Breakout Filters

## Trend Filter

The breakout strategy uses fast and slow EMA lines.

For a buy:

```text
fast EMA must be above slow EMA
```

For a sell:

```text
fast EMA must be below slow EMA
```

This avoids buying a breakout when the bigger direction is still weak.

## Trend Gap Filter

It also checks that the two EMA lines are not almost equal.

If they are too close:

```text
trend is weak or unclear
do nothing
```

This helps avoid trades in flat markets.

## Volatility Filter

Volatility means "how much price is moving".

The strategy avoids two bad zones:

```text
too little movement = no opportunity
too much movement   = chaos, bad fills, stop losses
```

So:

```text
volatility too low  = HOLD
volatility too high = HOLD
volatility normal   = strategy may trade
```

## Shorts

The breakout strategy can short if `allow_shorts: true`.

Short means:

```text
SELL first, hoping price goes down
BUY later to close
```

This is futures behavior. It is not spot trading.

## What Happens After A Strategy Says BUY Or SELL

The signal goes through risk management.

Risk manager checks:

```text
Are we already at max open positions?
Would this trade risk too much?
Have we hit max daily loss?
Is the stop loss valid?
```

Only then does the bot place or simulate an order.

So the flow is:

```text
candles -> strategy -> signal -> risk manager -> executor -> order
```

## Stop Loss And Take Profit

The strategy does not directly set stop loss and take profit.

The simulation runner uses config values:

```text
simulation.stop_loss_percent
simulation.take_profit_percent
```

Example:

```text
entry price = 100
stop loss   = 1%
take profit = 2%

long stop   = 99
long target = 102
```

For shorts it is reversed:

```text
short entry = 100
short stop  = 101
short target = 98
```

## What To Watch In Reports

After running:

```powershell
.\task.ps1 report
```

check:

```text
reports/local_test/summary.json
reports/local_test/trades.csv
reports/local_test/signals.csv
reports/local_test/equity_curve.csv
```

Important fields:

```text
return_percent       = total result
total_trades         = how often it traded
win_rate_percent     = percent of winning trades
profit_factor        = gross profit divided by gross loss
max_drawdown_percent = worst equity drop
```

High return alone is not enough. A strategy can make money in one run and still be bad if drawdown is huge or results only work in one market regime.

## Simple Mental Model

EMA Cross:

```text
"A trend may be starting."
```

RSI Mean Reversion:

```text
"Price stretched too far, maybe it bounces back."
```

Breakout:

```text
"Price escaped a range, and filters say the move may be real."
```

## Current Practical Advice

Use `breakout` first. It has the most filters and the best current test coverage.

Use `ema_cross` as a simple baseline.

Use `rsi_mean_reversion` carefully, because it can fight strong trends.

Before trusting any strategy:

```powershell
.\task.ps1 report
.\task.ps1 batch
.\task.ps1 test
```

Then inspect the report files. Do not judge only from one profitable run.
