import asyncio
import os
import subprocess
from datetime import datetime
from io import BytesIO
from uuid import uuid4

from helpers import (
    DATABASE_NAME,
    DEV_ID,
    SPAM_CACHE,
    convert_makrs_to_md_file,
    get_session,
    init_database,
)
from queries import (
    db_delete_all_marks,
    db_delete_all_students,
    db_delete_all_subjects,
    db_get_all_subjects,
    get_all_users,
    get_marks_by_subject,
    get_student,
    get_subject_by_name,
    get_user_from_db,
)
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler


def verify_admin(func):
    async def inner_func(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        query = update.inline_query
        user_id = query.from_user.id if query else update.message.from_user.id
        user = get_user_from_db(get_session(context), user_id)
        if user and user.is_admin or user_id == DEV_ID:
            return await func(update, context, *args, **kwargs)

    return inner_func


def verify_bot_owner(func):
    async def inner_func(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        query = update.inline_query
        user_id = query.from_user.id if query else update.message.from_user.id
        user = get_user_from_db(get_session(context), user_id)
        if user and user_id == DEV_ID:
            return await func(update, context, *args, **kwargs)

    return inner_func


@verify_admin
async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "send the message that want to send it public, or cancel by /cancel"
    )
    return 1


async def get_public_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    context.application.create_task(send_public_message_task(update, context, msg))
    await update.message.reply_text("The message on it's way...", quote=True)
    return ConversationHandler.END


async def send_message_async(user_id, message: Message):
    try:
        await message.copy(user_id)
    except TelegramError:
        pass


async def send_public_message_task(
    update: Update, context: ContextTypes.DEFAULT_TYPE, message: Message
):
    query = update.callback_query
    user_id = query.message.chat_id if query else update.message.chat_id
    customers = get_all_users(get_session(context))
    for indx, user in enumerate(customers):
        if indx % 20 == 0 and indx:
            await asyncio.sleep(1)
        await send_message_async(user.telegram_id, message)
    await context.bot.send_message(user_id, "تم الإرسال إلى جميع المستخدمين بنجاح!")


@verify_admin
async def get_total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"{len(get_all_users(get_session(context)))}")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != DEV_ID:
        return
    await update.message.reply_text("the task has been canceled...", quote=True)
    return ConversationHandler.END


@verify_admin
async def send_db_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_db_backup(context)


async def send_db_backup(context: ContextTypes.DEFAULT_TYPE):
    backup_filename = "backup{}.sqlite3".format(datetime.now().strftime("%Y%m%d%H%M%S"))
    os.system("cp {} {}".format(DATABASE_NAME, backup_filename))
    await context.bot.send_document(DEV_ID, backup_filename)
    os.system("rm {}".format(backup_filename))


@verify_admin
async def clear_spam_cache(update: Update, context):
    SPAM_CACHE.clear()
    await update.message.reply_text("Cache has been cleared successfully...")


@verify_admin
async def exec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    output = subprocess.check_output(context.args)
    try:
        await update.message.reply_text(
            "```\n{}\n```".format(output.decode("utf-8")),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
    except TelegramError:
        bytes_io = BytesIO()
        bytes_io.write(output.encode("utf-8"))

        await context.bot.send_document(
            DEV_ID, bytes_io.getvalue(), filename="output_{}.txt".format(uuid4())
        )


@verify_admin
async def update_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.reply_to_message.document
    if not document.file_name.endswith(".sqlite3"):
        await update.message.reply_text("file should be end with .sqlite3")
    file = await context.bot.get_file(document)
    path = await file.download_to_drive(document.file_name)
    path.rename(DATABASE_NAME)
    init_database(context.bot_data)
    await update.message.reply_text("Database updated successfully...")


@verify_admin
async def add_to_white_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_whitelisted = True
    await update.message.reply_text("Done")


@verify_admin
async def remove_white_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_whitelisted = False
    await update.message.reply_text("Done")


@verify_admin
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_blocked = True
    await update.message.reply_text("Done")


@verify_admin
async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_blocked = False
    await update.message.reply_text("Done")


@verify_bot_owner
async def add_new_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_admin = True
    await update.message.reply_text("Done")


@verify_bot_owner
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        user = get_user_from_db(session, user_id)
        user.is_admin = False
    await update.message.reply_text("Done")


@verify_admin
async def get_from_db_by_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_id = context.args[0]
    DbSession = get_session(context)
    with DbSession.begin() as session:
        student = get_student(session, student_id)
        marks = student.subjects_marks
        lst = []
        for mark in marks:
            lst.append(mark.subject.name)
            lst.append("{} {} {}".format(mark.amali, mark.nazari, mark.total))
    await update.message.reply_text("\n".join(lst))


@verify_admin
async def get_from_db_by_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subject_name = " ".join(context.args)

    with get_session(context).begin() as session:
        subject = get_subject_by_name(session, subject_name)
        if not subject:
            await update.message.reply_text("this subject name is not exist")
            subjects = db_get_all_subjects(session)
            await update.message.reply_text(
                "\n".join(f"`{subject.name}`" for subject in subjects),
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return

        marks = get_marks_by_subject(session, subject.id)
        marks.sort(key=lambda x: x.student.name)
    md_bytes = convert_makrs_to_md_file(subject, marks)
    await context.bot.send_document(DEV_ID, md_bytes, filename=f"{subject.name}.txt")


@verify_admin
async def get_all_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_session(context).begin() as session:
        subjects = db_get_all_subjects(session)
        await update.message.reply_text(
            "\n".join(f"`{subject.name}`" for subject in subjects),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        for subject in subjects:
            marks = get_marks_by_subject(session, subject.id)
            marks.sort(key=lambda x: x.student.name)
            md_bytes = convert_makrs_to_md_file(subject, marks)
            await context.bot.send_document(
                DEV_ID, md_bytes, filename=f"{subject.name}.txt"
            )
            await asyncio.sleep(1)


@verify_admin
async def download_this_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.reply_to_message.document
    file = await document.get_file()
    path = await file.download_to_drive(document.file_name)

    await update.message.reply_text(
        "File has been downloaded successfully at: `{}`".format(path.absolute()),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@verify_admin
async def delete_all_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_session(context).begin() as session:
        db_delete_all_marks(session)
        db_delete_all_subjects(session)
        db_delete_all_students(session)
    await update.message.reply_text("done, all students has been deleted!")


@verify_admin
async def admin_help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    output = (
        "/send_db_backup (sends current db file)",
        "/update_database [reply to .sqlite3 file] (replace db file with sended one)",
        "/clear_spam_cache (clear the cache if something goes wrong)",
        "/in_range x y (fetch students between x, y)",
        "/lazy_in_range x y z (fetch students that haven't been updated "
        "since z minutes otherwise get results from the db)",
        "/exec command (execute a command)",
        "/get_db_len (get the number of regestred users in the bot)",
        "/add_white_list [userid]",
        "/remove_white_list [userid]",
        "/add_admin [userid]",
        "/remove_admin [userid]",
        "/block_user [user_id]",
        "/unblock_user [user_id]",
        "/delete_all_students (delete all stored students and their marks)",
        "/get_from_db_by_student_id [university id] (get result from db only)",
        "/get_from_db_by_subject [subject name]",
        "/download_this_file [reply to file] (it will download it to it's local storage)",
        "/get_all_subjects (get all stored marks of all subjects, in md format)",
        "/admin_help (show this message)",
    )
    await update.message.reply_text("\n\n".join(output))
