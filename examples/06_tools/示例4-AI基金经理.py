import asyncio
import logging
import json
import random
from typing import List, Dict, Any

from alphora.agent import BaseAgent
from alphora.models import OpenAILike
from alphora.tools import tool, ToolRegistry, ToolExecutor
from alphora.models.llms.types import ToolCall

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("Quant_Agent")

# --- 0. 全局模拟环境 (The Simulation State) ---
# 这里保存着 Agent 无法直接修改的“客观事实”
class MarketSimulation:
    def __init__(self):
        self.day = 1
        self.cash = 100000.0  # 初始本金 10万
        self.holdings = 0     # 持股数量
        self.stock_price = 100.0 # 初始股价
        self.history = []     # 记录净值变化

    def next_day(self):
        """推进时间：股价随机游走"""
        self.day += 1
        # 随机波动率：-8% 到 +8% 之间剧烈波动
        change_pct = random.uniform(-0.08, 0.08)

        # 引入“黑天鹅”事件 (5% 概率暴涨或暴跌 15%)
        if random.random() < 0.05:
            change_pct *= 2.5

        self.stock_price = self.stock_price * (1 + change_pct)
        return change_pct

    def get_equity(self):
        return self.cash + (self.holdings * self.stock_price)

# 初始化单例
SIM = MarketSimulation()

# --- 1. 交易工具集 ---

@tool
def get_daily_market_info():
    """
    [每日必看] 获取当天的市场行情数据。
    包含：当前股价、相对强弱指标(RSI)、以及市场传闻。
    """
    price = SIM.stock_price

    # 简单的随机指标生成，用来迷惑或辅助 Agent
    rsi = random.randint(20, 90)
    sentiment = "NEUTRAL"
    if rsi > 80: sentiment = "OVERBOUGHT (超买风险)"
    if rsi < 20: sentiment = "OVERSOLD (超卖机会)"

    logger.info(f"📅 [Day {SIM.day}] 开盘价: ${price:.2f} | RSI: {rsi}")

    return {
        "day": SIM.day,
        "current_price": round(price, 2),
        "technical_indicator_rsi": rsi,
        "market_sentiment": sentiment,
        "news_flash": random.choice([
            "分析师看好科技股前景",
            "通胀数据引发担忧",
            "公司财报即将发布",
            "大股东减持传闻",
            "静淡无消息"
        ])
    }

@tool
def get_account_status():
    """
    [账户查询] 查询当前可用现金、持仓数量和总资产净值。
    """
    equity = SIM.get_equity()
    roi = ((equity - 100000) / 100000) * 100

    logger.info(f"💰 账户状态: 现金=${SIM.cash:.0f}, 持仓={SIM.holdings}, 总资产=${equity:.0f} (ROI: {roi:.2f}%)")
    return {
        "cash_balance": round(SIM.cash, 2),
        "shares_held": SIM.holdings,
        "total_equity": round(equity, 2),
        "current_roi_percent": round(roi, 2)
    }

@tool
def place_market_order(action: str, quantity: int):
    """
    [下单交易] 执行买入或卖出。
    - action: 'BUY' 或 'SELL'
    - quantity: 数量 (必须大于0)
    """
    current_price = SIM.stock_price
    cost = current_price * quantity

    logger.info(f"⚡ 尝试交易: {action} {quantity} 股 @ ${current_price:.2f}")

    if action == "BUY":
        if SIM.cash >= cost:
            SIM.cash -= cost
            SIM.holdings += quantity
            return {"status": "SUCCESS", "msg": f"买入成功。消耗现金 ${cost:.2f}"}
        else:
            return {"status": "FAILED", "msg": "资金不足 (Insufficient Funds)"}

    elif action == "SELL":
        if SIM.holdings >= quantity:
            SIM.cash += cost
            SIM.holdings -= quantity
            return {"status": "SUCCESS", "msg": f"卖出成功。获得现金 ${cost:.2f}"}
        else:
            return {"status": "FAILED", "msg": "持仓不足 (Not enough shares)"}

    return {"status": "ERROR", "msg": "Invalid Action"}

@tool
def hold_position(reason: str):
    """
    [观望] 当市场不明朗时，选择不操作，直接结束当天的交易。
    """
    logger.info(f"🛑 今日空仓/持仓不动。原因: {reason}")
    return {"status": "SKIPPED", "msg": "Day passed without trading."}


# --- 2. 自动操盘主循环 ---

async def run_autonomous_trader():
    registry = ToolRegistry()
    registry.register(get_daily_market_info)
    registry.register(get_account_status)
    registry.register(place_market_order)
    registry.register(hold_position)

    executor = ToolExecutor(registry)
    llm = OpenAILike()

    # --- System Prompt: 贪婪而理性的交易员 ---
    system_prompt = """你是一个高频量化交易机器人。你的目标是在 7 天内最大化投资回报率 (ROI)。
初始资金：$100,000。

**每日策略流程**：
1. **获取信息**：调用 `get_daily_market_info` 和 `get_account_status`。
2. **分析决策**：
   - 价格低且 RSI 低（超卖） -> **BUY** (买入)。
   - 价格高且 RSI 高（超买） -> **SELL** (卖出)。
   - 趋势不明 -> **HOLD** (观望)。
3. **风控**：
   - 严禁透支。
   - 不要总是满仓，保留现金应对波动。

注意：这是多日连续交易，今天的决策会影响明天。请理性操作。
"""

    agent = BaseAgent(llm=llm)
    prompt = agent.create_prompt(
        system_prompt=system_prompt,
        enable_memory=True    # 必须开启记忆，否则它记不住昨天的操作
    )

    # 模拟 7 个交易日
    total_days = 30

    print(f"\n🚀 [回测开始] 初始资金: $100,000 | 初始股价: $100.00")

    for day in range(1, total_days + 1):
        print(f"\n--------- 📅 第 {day} 交易日 ---------")

        # 每一天开始时，Agent 收到当天的“唤醒指令”
        daily_query = f"今天是第 {day} 天。请决定交易策略。如果无需交易，请不要调用工具，请直接输出一段当日总结思考，将自动进入下一天。"

        # --- Agent 思考与行动 (Turn) ---
        # 我们允许 Agent 在同一天内多步思考（查行情 -> 查钱 -> 下单）

        for _ in range(5):

            response = await prompt.acall(
                query=daily_query,
                tools=registry.get_openai_tools_schema(),
                system_prompt="请完成今日交易决策。"
            )

            mm = prompt.get_memory()

            if response:
                tool_calls = response

                # 执行 Agent 的决策
                await executor.execute(tool_calls, memory_manager=mm)

                # 打印它干了什么
                for tc in tool_calls:
                    fname = tc.get('function').get('name')
                    args = json.loads(tc.get('function').get('arguments'))
                    if fname == "place_market_order":
                        print(f"   🔴 [下单]: {args.get('action')} {args.get('quantity')} 股")
                    elif fname == "hold_position":
                        print(f"   🔵 [观望]: {args.get('reason')}")
            else:
                print(f'选择结束当天--{response.content}')
                break

        # --- 交易日结束，模拟器推进时间 ---
        if day < total_days:
            change = SIM.next_day()
            print(f"   🌙 收盘总结: 股价变动 {change*100:+.2f}% -> 新股价 ${SIM.stock_price:.2f}")

    # --- 最终结算 ---
    final_equity = SIM.get_equity()
    final_roi = ((final_equity - 100000) / 100000) * 100

    print(f"\n📊 [最终回测报告]")
    print(f"   最终资产: ${final_equity:,.2f}")
    print(f"   收益率:   {final_roi:+.2f}%")

    mm.save_history(file_path='基金经理的记忆.txt')

    if final_roi > 0:
        print("   🏆 评价: 盈利！你是合格的交易员。")
    else:
        print("   💀 评价: 亏损。建议回炉重造。")

if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_trader())
    except Exception as e:
        logger.error(f"Simulation Error: {e}", exc_info=True)