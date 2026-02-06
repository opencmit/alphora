from alphora.models import OpenAILike
from alphora_community.tools.files.image_reader import ImageReaderTool

from alphora_community.tools.files.file_viewer import FileViewerAgent
from alphora.sandbox import Sandbox, StorageConfig, LocalStorage


py_code = """
import pandas as pd


df = pd.read_excel('test.xlsx')
print(df)
"""


if __name__ == "__main__":
    import asyncio

    async def main():
        # 示例用法
        llm = OpenAILike(model_name='qwen-vl-plus', is_multimodal=True)

        sb_storage_config = StorageConfig(local_path='/Users/tiantiantian/临时/sandbox/my_sandbox')
        sb_storage = LocalStorage(config=sb_storage_config)
        sb = Sandbox.create_docker(base_path='/Users/tiantiantian/临时/sandbox', storage=sb_storage, sandbox_id='123456')

        await sb.start()

        # res = await sb.install_package(package='pandas')
        # print(res)
        #
        # exe_res = await sb.execute_code(code=py_code)
        # print(exe_res)

        tool = ImageReaderTool(
            llm=llm,
            sandbox=sb
        )

        fv = FileViewerAgent(
            sandbox=sb,
        )

        print(await sb.list_files())

        # 描述图片
        # result = await tool.describe("WechatIMG3494.jpg")
        # print(f"图片描述: {result}")

        result = await fv.view_file(file_path='test.xlsx')
        print(result)

        await sb.destroy()

    asyncio.run(main())

