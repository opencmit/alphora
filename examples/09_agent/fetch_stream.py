"""
调用第三方API
"""

from alphora.agent import BaseAgent
from alphora.server.openai_request_body import OpenAIRequest


class FetchAgent(BaseAgent):

    async def main(self, query):
        payload = {"messages": [{"role": "user", "content": query}],
                   "session_id": "123"}

        resp = await self.afetch_stream(url='http://127.0.0.1:8011/excelqa/chat/completions',
                                        payload=payload)

        return resp


async def main():
    agent = FetchAgent()
    resp = await agent.main(query='你好')
    return resp


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
