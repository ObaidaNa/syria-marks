import asyncio
from dataclasses import dataclass
from time import time
from typing import List

import aiohttp
from telegram import Message

UNIVERSITY_URL = "https://exam.homs-univ.edu.sy/exam-it/re.php"


@dataclass
class WebStudentResponse:
    student_number: int
    html_page: bytes


async def multi_async_request(
    numbers: List[int], recurse_limit: int = 2, message: Message = None
) -> List[WebStudentResponse]:
    async with aiohttp.ClientSession() as session:
        requested_cnt = len(numbers)
        gathered_cnt = 0 
        gathered: List[WebStudentResponse] = []
        message_last_update = time()
        progress_bar = "▫️▫️▫️▫️▫️▫️▫️▫️▫️▫️"
        progress_bar_end = 0
        for number in numbers:
            result  = await one_req(int(number), session, recurse_limit)
            gathered.append(result)
            gathered_cnt = gathered_cnt + 1
            if message and time() - message_last_update >= 1:
                while progress_bar_end < 10 and gathered_cnt / requested_cnt * 10 >= progress_bar_end + 1:
                    progress_bar = progress_bar[:progress_bar_end * 2] + '◾️' + progress_bar[(progress_bar_end + 1) * 2:]
                    progress_bar_end = progress_bar_end +1
                await message.edit_text(
                    f"⏳ يتم جلب المعلومات من الموقع ...\n\n{gathered_cnt} / {requested_cnt}  [{progress_bar}]",
                    reply_markup=message.reply_markup
                )
                message_last_update = time()
    return gathered


async def one_req(
    number, session: aiohttp.ClientSession, recurse_limit: int
) -> WebStudentResponse:
    if recurse_limit <= 0:
        raise Exception("uncompleted request, try again later")

    try:
        async with session.post(UNIVERSITY_URL, data={"number1": number}) as req:
            res_data = await req.read()
        if req.status != 200:
            await asyncio.sleep(1)
            return await one_req(number, session, recurse_limit - 1)
        return WebStudentResponse(number, res_data)
    except Exception:
        await asyncio.sleep(1)
        return await one_req(number, session, recurse_limit - 1)
