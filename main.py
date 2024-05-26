import logging
import os
import re
import json
from telegram import Update, Message, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from flask import Flask, request

# Configuraciones del bot
BOT_TOKEN = os.getenv('BOT_TOKEN', '7291468384:AAGJdFTXF7pfgfPEOMiJesbjOBVrD4EtGNo')
USER_ID = 7169978359  # ID confirmado del usuario destinatario
GROUPS_FILE = 'groups.json'

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Diccionario para almacenar los grupos en los que el bot ha recibido mensajes
groups = {}

# Estados para el manejador de conversación
GROUP_NAME, MESSAGE = range(2)

def save_groups():
    with open(GROUPS_FILE, 'w', encoding='utf-8') as file:
        json.dump(groups, file)

def load_groups():
    global groups
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as file:
            groups = json.load(file)
    except FileNotFoundError:
        groups = {}

async def forward_message(update: Update, context: CallbackContext) -> None:
    user = update.message.from_user
    user_name = user.username if user.username else user.first_name
    user_id = user.id
    chat_type = update.message.chat.type

    # Reenvía mensajes de texto y fotos
    if update.message.text and not update.message.text.startswith('/'):
        if chat_type in ['group', 'supergroup']:
            group_name = update.message.chat.title
            message_to_forward = (
                f'Grupo: {group_name}\n'
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {update.message.text}'
            )
        else:
            message_to_forward = (
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {update.message.text}'
            )
        try:
            await context.bot.send_message(chat_id=USER_ID, text=message_to_forward)
        except Exception as e:
            logging.error(f"Error enviando mensaje a USER_ID: {e}")

        # Añadir el grupo a la lista de grupos si es un grupo
        if chat_type in ['group', 'supergroup']:
            groups[update.message.chat.title] = update.message.chat.id
            save_groups()

            # Escribir el mensaje en el archivo correspondiente al grupo
            with open(f'{update.message.chat.title}.txt', 'a', encoding='utf-8') as file:
                file.write(f'{user_name} - #{user_id}\n{update.message.text}\n\n')

    elif update.message.photo:
        photo_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        if chat_type in ['group', 'supergroup']:
            group_name = update.message.chat.title
            caption_to_forward = (
                f'Grupo: {group_name}\n'
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {caption}'
            )
        else:
            caption_to_forward = (
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {caption}'
            )
        try:
            await context.bot.send_photo(chat_id=USER_ID, photo=photo_id, caption=caption_to_forward)
        except Exception as e:
            logging.error(f"Error enviando foto a USER_ID: {e}")

        # Añadir el grupo a la lista de grupos si es un grupo
        if chat_type in ['group', 'supergroup']:
            groups[update.message.chat.title] = update.message.chat.id
            save_groups()

async def send_groups(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        if groups:
            groups_list = '\n'.join([f'{title} - {chat_id}' for title, chat_id in groups.items()])
            await context.bot.send_message(chat_id=USER_ID, text=f'Grupos:\n{groups_list}')
        else:
            await context.bot.send_message(chat_id=USER_ID, text='El bot no está en ningún grupo.')

async def start(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        await update.message.reply_text('Bot iniciado. Usa /grupos para listar los grupos y /send para enviar un mensaje a un grupo o usuario.')
    else:
        await update.message.reply_text('Hola! Usa /enviar para enviarme un mensaje, foto o video.')

async def test_message(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        try:
            await context.bot.send_message(chat_id=USER_ID, text="Mensaje de prueba desde el bot.")
        except Exception as e:
            await update.message.reply_text(f"Error enviando mensaje a USER_ID: {e}")

async def get_id(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        user_id = update.message.from_user.id
        await update.message.reply_text(f"Tu ID de usuario es: {user_id}")

async def join_group(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        try:
            invite_link = context.args[0]
            if re.match(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', invite_link):
                await context.bot.send_message(chat_id=USER_ID, text=f'Para unir el bot al grupo o canal, utiliza el siguiente enlace:\n{invite_link}')
            else:
                await context.bot.send_message(chat_id=USER_ID, text='El enlace proporcionado no es válido.')
        except IndexError:
            await context.bot.send_message(chat_id=USER_ID, text='Uso: /join https://t.me/tu_enlace')

async def start_send(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        if update.message.reply_to_message:
            context.user_data['reply_message'] = update.message.reply_to_message
            await update.message.reply_text('Proporciona el nombre del grupo o el @ del usuario al que deseas enviar el mensaje:')
            return GROUP_NAME
        else:
            await update.message.reply_text('Por favor, responde al mensaje que deseas reenviar y luego usa /send.')
            return ConversationHandler.END

async def start_enviar(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id != USER_ID:
        if update.message.reply_to_message:
            context.user_data['reply_message'] = update.message.reply_to_message
            await update.message.reply_text('Enviando tu mensaje...')
            return await send_message_to_user(context, update.message)
        else:
            await update.message.reply_text('Por favor, responde al mensaje que deseas reenviar y luego usa /enviar.')
            return ConversationHandler.END

async def receive_group_name(update: Update, context: CallbackContext) -> int:
    if update.message.chat.id == USER_ID:
        group_or_user = update.message.text
        context.user_data['group_or_user'] = group_or_user

        # Verificar si es un grupo o un usuario
        if group_or_user in groups:
            context.user_data['target_id'] = groups[group_or_user]
            await update.message.reply_text(f'Grupo "{group_or_user}" encontrado. Enviando el mensaje respondido...')
            return await send_message_to_target(context, update.message)
        elif group_or_user.startswith('@'):
            context.user_data['target_id'] = group_or_user
            await update.message.reply_text(f'Usuario "{group_or_user}" encontrado. Enviando el mensaje respondido...')
            return await send_message_to_target(context, update.message)
        else:
            try:
                chat = await context.bot.get_chat(group_or_user)
                context.user_data['target_id'] = chat.id
                await update.message.reply_text(f'Chat "{chat.title or chat.username}" encontrado. Enviando el mensaje respondido...')
                return await send_message_to_target(context, update.message)
            except Exception as e:
                await update.message.reply_text(f'Error: No se pudo encontrar el grupo o usuario "{group_or_user}".')
                logging.error(f"Error encontrando el grupo o usuario: {e}")
                return ConversationHandler.END

async def send_message_to_target(context: CallbackContext, message: Message) -> int:
    target_id = context.user_data['target_id']
    reply_message = context.user_data.get('reply_message', None)

    if reply_message:
        if reply_message.text:
            await context.bot.send_message(chat_id=target_id, text=reply_message.text)
        elif reply_message.photo:
            await context.bot.send_photo(chat_id=target_id, photo=reply_message.photo[-1].file_id, caption=reply_message.caption)
        elif reply_message.video:
            await context.bot.send_video(chat_id=target_id, video=reply_message.video.file_id, caption=reply_message.caption)
        else:
            await message.reply_text("Tipo de mensaje no soportado.")
    else:
        await message.reply_text("No se ha encontrado el mensaje para reenviar.")

    await message.reply_text(f'Mensaje enviado a "{context.user_data["group_or_user"]}".')
    return ConversationHandler.END

async def send_message_to_user(context: CallbackContext, message: Message) -> int:
    target_id = USER_ID
    reply_message = context.user_data.get('reply_message', None)
    user = message.from_user
    user_name = user.username if user.username else user.first_name
    user_id = user.id

    if reply_message:
        if reply reply_message.text:
            text_to_send = (
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {reply_message.text}'
            )
            await context.bot.send_message(chat_id=target_id, text=text_to_send)
        elif reply_message.photo:
            caption_to_send = (
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {reply_message.caption or ""}'
            )
            await context.bot.send_photo(chat_id=target_id, photo=reply_message.photo[-1].file_id, caption=caption_to_send)
        elif reply_message.video:
            caption_to_send = (
                f'User: {user_name} - #{user_id}\n'
                f'Mensaje: {reply_message.caption or ""}'
            )
            await context.bot.send_video(chat_id=target_id, video=reply_message.video.file_id, caption=caption_to_send)
        else:
            await message.reply_text("Tipo de mensaje no soportado.")
    else:
        await message.reply_text("No se ha encontrado el mensaje para reenviar.")

    await message.reply_text('Mensaje enviado al usuario autorizado.')
    return ConversationHandler.END

async def get_group_members(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        if len(context.args) == 0:
            await update.message.reply_text('Uso: /usuarios_grupo <nombre o ID del grupo>')
            return

        group_identifier = ' '.join(context.args)
        group_id = groups.get(group_identifier, group_identifier)
        try:
            members = await context.bot.get_chat_members(group_id)
            members_list = '\n'.join([f'{member.user.first_name} - #{member.user.id}' for member in members])
            await context.bot.send_message(chat_id=USER_ID, text=f'Miembros del grupo {group_identifier}:\n{members_list}')
        except Exception as e:
            logging.error(f"Error obteniendo los miembros del grupo: {e}")
            await context.bot.send_message(chat_id=USER_ID, text='Error obteniendo los miembros del grupo.')

async def get_group_admins(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        if len(context.args) == 0:
            await update.message.reply_text('Uso: /admins_grupo <nombre o ID del grupo>')
            return

        group_identifier = ' '.join(context.args)
        group_id = groups.get(group_identifier, group_identifier)
        try:
            admins = await context.bot.get_chat_administrators(group_id)
            admins_list = '\n'.join([f'{admin.user.first_name} - #{admin.user.id}' for admin in admins])
            await context.bot.send_message(chat_id=USER_ID, text=f'Administradores del grupo {group_identifier}:\n{admins_list}')
        except Exception as e:
            logging.error(f"Error obteniendo los administradores del grupo: {e}")
            await context.bot.send_message(chat_id=USER_ID, text='Error obteniendo los administradores del grupo.')

async def cancel(update: Update, context: CallbackContext) -> None:
    if update.message.chat.id == USER_ID:
        await update.message.reply_text('Operación cancelada.')
        return ConversationHandler.END

# Inicializar la aplicación Flask
app = Flask(__name__)

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook() -> str:
    update = Update.de_json(request.get_json(force=True), bot)
    application.process_update(update)
    return 'ok'

if __name__ == '__main__':
    load_groups()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler_send = ConversationHandler(
        entry_points=[CommandHandler('send', start_send)],
        states={
            GROUP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_group_name)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    conv_handler_enviar = ConversationHandler(
        entry_points=[CommandHandler('enviar', start_enviar)],
        states={},
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler_send)
    application.add_handler(conv_handler_enviar)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("grupos", send_groups))
    application.add_handler(CommandHandler("join", join_group))
    application.add_handler(CommandHandler("test", test_message))
    application.add_handler(CommandHandler("get_id", get_id))
    application.add_handler(CommandHandler("usuarios_grupo", get_group_members))
    application.add_handler(CommandHandler("admins_grupo", get_group_admins))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_message))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, forward_message))

    app.run(port=5000)
