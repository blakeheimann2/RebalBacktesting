import unittest
import backtrader as bt
from datetime import datetime
import copy
import backtrader.analyzers as bta
import backtrader.observers as bto
from app.RebalStrategy import RebalanceStrategy, AcctValue, printTradeAnalysis
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pandas_datareader.data as web
pd.set_option('display.max_rows', 1000)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 1000)

class TestStrategy(unittest.TestCase):
    def testStrat(self):
        startcash = 100000
        cerebro = bt.Cerebro()
        strat_params = [
            ('AGG', 10),
            ('IEMG', 10),
            ('IAU', 10),
            ('MBB', 10),
            ('IXUS', 10),
            ('IJH', 10),
            ('IJR', 10),
            ('IVW', 10),
            ('IUSV', 10),
            ('IGV', 10),
        ]
        symbol_list = [x[0] for x in strat_params]
        dont_plot = []
        # Add our strategy
        cerebro.addstrategy(RebalanceStrategy, assets=strat_params)

        is_first=True
        for tick in symbol_list:
            data = bt.feeds.YahooFinanceData(dataname=tick,
                                             fromdate=datetime(2017, 1, 1),
                                             todate=datetime(2020, 9, 1))
            if tick not in dont_plot:
                if is_first:
                    data.plotinfo.plotlinelabels = False
                    data.plotinfo.plotylimited = False
                    data.plotinfo.sameaxis = True
                    data_main_plot = data
                    is_first = False
                else:
                    #data.compensate(last_data)
                    data.plotinfo.plotmaster = data_main_plot
                    data.plotinfo.plotlinelabels = False
                    data.plotinfo.plotylimited = False
                    data.plotinfo.sameaxis = True
            else:
                data.plotinfo.plot = False
            cerebro.adddata(data)
            #last_data = copy.deepcopy(data)

        # Set our desired cash start and run settings
        cerebro.broker.setcash(startcash)
        cerebro.addanalyzer(bta.SharpeRatio, _name='mysharpe')
        cerebro.addanalyzer(bta.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bta.TimeDrawDown, _name='drawdowntime')
        cerebro.addanalyzer(bta.PositionsValue, _name='positionsValue', cash=True)  ##
        cerebro.addanalyzer(bta.Returns, _name='returns')
        cerebro.addanalyzer(bta.Transactions, _name='trxns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="ta")
        cerebro.broker.set_checksubmit(False)

        cerebro.addobserver(AcctValue)
        cerebro.addobservermulti(bto.BuySell, plotlinelabels=False, plotname=False)
        # Run the backtest
        results = cerebro.run(stdstats=False)
        cerebro.plot(iplot=True, volume=False)

        # Get final portfolio Value
        portfolio_value = cerebro.broker.getvalue()
        pnl = portfolio_value - startcash
        #self.assertEquals(pnl, 78239.86999999997)

        # Analyze Results
        analyzers = results[0].analyzers
        trxns = analyzers.trxns.get_analysis()
        trades = analyzers.ta.get_analysis()
        tot_returns = analyzers.returns.get_analysis()
        sharpe = analyzers.mysharpe.get_analysis()
        positionvals = analyzers.positionsValue.get_analysis()
        position_hist = pd.DataFrame(positionvals).T
        position_hist.columns = symbol_list + ["Cash"]
        portfoliovals = position_hist.sum(axis=1)
        returns = np.log(portfoliovals / portfoliovals.shift(1))[1:]
        max_drawdown = analyzers.drawdown.get_analysis()

        # Get SPY returns to compare
        spy_st = pd.Series(returns.cumsum()).index[0]
        spy_end = pd.Series(returns.cumsum()).index[-1]
        SPY_df = web.DataReader('SPY', 'yahoo', spy_st, spy_end)
        SPY_returns = pd.Series(np.log(SPY_df.Close / SPY_df.Close.shift(1)).cumsum())
        # Get SPY $ Portfolio Value
        SPY_portfolio_values = (startcash / SPY_df.Close[0]) * SPY_df.Close

        # Plot Returns Comparison
        plt.clf()
        pd.Series(returns.cumsum()).plot(label="Portfolio Returns")
        pd.Series(SPY_returns).plot(label="SPY Returns")
        plt.title("Portfolio Returns")
        plt.ylabel("Log Returns")
        plt.legend()
        plt.show()

        # Plot Returns Comparison
        plt.clf()
        pd.Series(portfoliovals).plot(label="Portfolio $ Value")
        pd.Series(SPY_portfolio_values).plot(label="SPY Portfolio $ Value")
        plt.title("Portfolio Value")
        plt.ylabel("Dollars")
        plt.legend()
        plt.show()

        # Print Out the Backtest Analysis
        # for x in results[0].analyzers:
        #     x.print()

        print('Final Portfolio Value: ${}'.format(portfolio_value))
        print('Portfololio PnL: ${}'.format(pnl))
        print("Portfolio Total Log Returns: {}".format(tot_returns["rtot"]))
        print("Portfolio Sharpe Ratio: {}".format(sharpe['sharperatio']))
        print(
            "Portfolio Max Drawdown: ${}, Time: {} days".format(max_drawdown.max["moneydown"], max_drawdown.max["len"]))
        print("---Compare to SPY---")
        print("SPY Portfolio Value: ${}".format(SPY_portfolio_values[-1]))
        print("SPY Portfolio Pnl: ${}".format(SPY_portfolio_values[-1] - startcash))
        print("SPY Total Log Returns: {}".format(SPY_returns[-1]))

        # Get Round Trip Trade Info
        printTradeAnalysis(trades)
        print("Portfolio History:")
        print(position_hist)

