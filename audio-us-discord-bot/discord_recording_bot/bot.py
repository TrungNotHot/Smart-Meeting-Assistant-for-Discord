import discord
import os
from dotenv import load_dotenv
from typing import Final
from costum_pycord import *  # Import CustomVoiceClient từ file bot_discord.py


load_dotenv("/home/trungnothot/Study/Thesis/audio-us-discord-bot/.env")
TOKEN: Final[str] = os.getenv('DISCORD_BOT_TOKEN')

# Khởi tạo bot
bot = discord.Bot(intents=discord.Intents.all())  
connections = {}



@bot.command()
async def record(ctx, use_websocket: bool = True):
    """Command để bắt đầu ghi âm, với tùy chọn WebSocket"""
    voice = ctx.author.voice

    if not voice:
        await ctx.respond("You aren't in a voice channel!")
        return
    
    vc = await voice.channel.connect(cls=CustomVoiceClient)
    connections.update({ctx.guild.id: vc})  # Lưu voice client vào cache
    vc.start_recording(use_websocket=use_websocket)  
    
    method = "WebSocket" if use_websocket else "HTTP"
    await ctx.respond(f"Started recording using {method} connection!")

@bot.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:  # Kiểm tra guild có trong cache không
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        await vc.disconnect()
        del connections[ctx.guild.id]  # Xóa guild khỏi cache
        await ctx.respond("Stopped recording!")
    else:
        await ctx.respond("I am currently not recording here.")

# Chạy bot
bot.run(token=TOKEN)