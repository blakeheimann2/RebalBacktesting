import backtrader as bt
from datetime import datetime, timedelta
import pandas as pd
import copy

from pypfopt.efficient_frontier import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns


class RebalanceStrategy(bt.Strategy):
    params = (('assets', list()),
              ('rebalance_months', [1,4,7,10]),)  #Rebalance every qtr

    def __init__(self):
        self.weight_chg = {}
        self.weights = {}
        self.last_weights = None
        self.date = datetime.fromordinal(int(self.datas[0].fromdate))
        self.day = 0
        self.prices = {}
        self.rebalance_dict = dict()
        for i, d in enumerate(self.datas):
            self.rebalance_dict[d] = dict()
            self.rebalance_dict[d]['rebalanced'] = False
            for asset in self.p.assets:
                if asset[0] == d._name:
                    self.weights[d._name] = asset[1]/100
                    self.weight_chg[d._name] = asset[1]/100
                    self.prices[d._name] = pd.Series(self.datas[i].close.array)
                    # start_dt = dt.fromordinal(int(self.datas[i].fromdate))
                    # end_dt = dt.fromordinal(int(self.datas[i].todate))
                    # self.prices[asset].set_index(pd.date_range(start=start_dt, end=end_dt))
                    self.rebalance_dict[d]['target_percent'] = asset[1]


    #Need to sell before buyings.., if weight chg neg, place order first
    def next(self):
        trades = []
        self.day += 1
        if self.date.month in self.p.rebalance_months and self.date.day ==1 and self.day >= 20:
            self.rebal()
        #print("CASH BAL: {}".format(self.broker.getcash()))
        for i, d in enumerate(self.datas):
            dt = d.datetime.datetime()
            dn = d._name
            pos = self.getposition(d).size
            if dt.month in self.p.rebalance_months:
                if self.rebalance_dict[d]['rebalanced'] == False:
                    if self.weight_chg[d._name] != 0.0:
                        trades.append((d, dt, dn, dt.month, self.rebalance_dict[d]['rebalanced'], pos, self.rebalance_dict[d]['target_percent']/100, self.weight_chg[d._name]))
                    if self.weight_chg[d._name] == 0.0:
                        self.rebalance_dict[d]['rebalanced'] = True

            if dt.month not in self.p.rebalance_months:
                self.rebalance_dict[d]['rebalanced'] = False

        trades = sorted(trades, key=lambda x: x[7], reverse=False)
        for trade_info in trades:
            (d, dt, dn, month, rebal_status, pos, tgt_wt, wt_chg) = trade_info
            if self.rebalance_dict[d]['rebalanced'] == False:
                if not (float(pos) == 0 and tgt_wt == 0):
                    self.order_target_percent(d, target=tgt_wt)
                    # Reset
                    print('{} Sending Order: {} | Month {} | Rebalanced: {} | Pos: {} | Weight: {} | Weight Chg: {}'.format(dt, dn, month, rebal_status, pos, tgt_wt, wt_chg))
            if dt.month not in self.p.rebalance_months:
                self.rebalance_dict[d]['rebalanced'] = False
        self.date = dt + timedelta(days=1)

    def rebal(self):
        prices = pd.DataFrame([self.prices[d._name][:self.day] for d in self.datas]).T
        prices.columns = [d._name for d in self.datas]
        avg_returns = expected_returns.mean_historical_return(prices)
        cov_mat = risk_models.sample_cov(prices)
        # get weights maximizing the Sharpe ratio
        ef = EfficientFrontier(avg_returns, cov_mat)
        self.last_weights = copy.deepcopy(self.weights)
        self.weights = ef.max_sharpe()
        self.weight_chg = pd.Series(self.weights) - pd.Series(self.last_weights)
        self.cleaned_weights = ef.clean_weights()
        for i, d in enumerate(self.datas):
            self.rebalance_dict[d] = dict()
            self.rebalance_dict[d]['rebalanced'] = False
            for asset in self.p.assets:
                if asset[0] == d._name:
                    self.rebalance_dict[d]['target_percent'] = self.weights[d._name] * 99 #less than 100%

    def notify_order(self, order):
        date = self.data.datetime.datetime().date()
        if order.status == order.Completed:
            print('{} >> Order Completed >> Stock: {},  Ref: {}, Size: {}, Price: {}'.format(
                date,
                order.data._name,
                order.ref,
                order.size,
                'NA' if not order.price else round(order.price, 5)
            ))
            self.rebalance_dict[order.data]['rebalanced'] = True
        else:
            print('{} >> Order Incomplete >> Stock: {},  Ref: {}, Size: {}, Price: {}, Status: {}'.format(
                date,
                order.data._name,
                order.ref,
                order.size,
                'NA' if not order.price else round(order.price, 5),
                order.Status[order.status]
            ))
            if order.size == 0:
                self.rebalance_dict[order.data]['rebalanced'] = True

    def notify_trade(self, trade):
        date = self.data.datetime.datetime().date()
        if trade.isclosed:
            print('{} >> Notify Trade >> Stock: {}, Close Price: {}, Profit, Gross {}, Net {}'.format(
                date,
                trade.data._name,
                trade.price,
                round(trade.pnl, 2),
                round(trade.pnlcomm, 2)))

        else:
            print('{} >> Notify Trade PENDING>> Stock: {}, Price {}, Status {}'.format(
                date,
                trade.data._name,
                trade.price,
                trade.status_names[trade.status]))


class AcctValue(bt.Observer):
    alias = ('Value',)
    lines = ('value',)

    plotinfo = {"plot": True, "subplot": True}

    def next(self):
        self.lines.value[0] = self._owner.broker.getvalue()




def printTradeAnalysis(tradeanalyzer):
    '''
    Function to print the Trade Analysis results in a nice format.
    '''
    total_open = tradeanalyzer.total.open
    total_closed = tradeanalyzer.total.closed
    total_won = tradeanalyzer.won.total
    total_lost = tradeanalyzer.lost.total
    win_streak = tradeanalyzer.streak.won.longest
    lose_streak = tradeanalyzer.streak.lost.longest
    pnl_net = round(tradeanalyzer.pnl.net.total,2)
    strike_rate = (total_won / total_closed) * 100
    h1 = ['Total Open', 'Total Closed', 'Total Won', 'Total Lost']
    h2 = ['Strike Rate','Win Streak', 'Losing Streak', 'PnL Net']
    r1 = [total_open, total_closed,total_won,total_lost]
    r2 = [round(strike_rate,2), win_streak, lose_streak, pnl_net]
    if len(h1) > len(h2):
        header_length = len(h1)
    else:
        header_length = len(h2)
    print_list = [h1,r1,h2,r2]
    row_format ="{:<15}" * (header_length + 1)
    print("Trade Analysis Results:")
    for row in print_list:
        print(row_format.format('',*row))

def printSQN(sqnanalyzer):
    sqn = round(sqnanalyzer.sqn,2)
    print('SQN: {}'.format(sqn))


def saveplots(cerebro, numfigs=1, iplot=True, start=None, end=None,
                  width=16, height=9, dpi=300, tight=True, use=None, file_path='', **kwargs):

        from backtrader import plot
        if cerebro.p.oldsync:
            plotter = plot.Plot_OldSync(**kwargs)
        else:
            plotter = plot.Plot(**kwargs)

        figs = []
        for stratlist in cerebro.runstrats:
            for si, strat in enumerate(stratlist):
                rfig = plotter.plot(strat, figid=si * 100,
                                    numfigs=numfigs, iplot=iplot,
                                    start=start, end=end, use=use)
                figs.append(rfig)

        for fig in figs:
            for f in fig:
                f.savefig(file_path, bbox_inches='tight')
        return figs


