import discord
import subprocess
import os
import re
from dotenv import load_dotenv

load_dotenv("/home/ec2-user/aiops/.env")

COMMAND_CHANNEL_ID = 1503302665369681980
Q_PATH = "/home/ec2-user/.local/bin/qchat"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Bot connected as {client.user}')
    print(f'📢 Listening for commands in channel: {COMMAND_CHANNEL_ID}')

@client.event
async def on_message(message):
    # Ignore own messages
    if message.author == client.user:
        return
    
    # Only respond in command channel
    if message.channel.id != COMMAND_CHANNEL_ID:
        return
    
    # Ignore empty messages
    if not message.content.strip():
        return
    
    user_query = message.content.strip()
    print(f'📩 Received: {user_query}')
    
    # Send "thinking" reaction
    await message.add_reaction('🤔')
    
    try:
        # Add cluster context to the query
        cluster_name = subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
        aws_region = os.getenv("AWS_REGION", "ap-south-1")
        
        full_prompt = f"""EKS Cluster: {cluster_name}
AWS Region: {aws_region}

User Query: {user_query}

Use the EKS cluster and region specified above."""
        
        # Call Q CLI with context
        result = subprocess.run(
            [Q_PATH, "chat", "-a", "--no-interactive"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HOME": "/home/ec2-user"}
        )
        
        output = result.stdout.strip() or result.stderr.strip() or "No response from Q"
        
        # Strip ANSI codes and Q CLI formatting
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)
        
        # Remove Q CLI specific formatting markers
        output = re.sub(r'\d+m', '', output)
        output = re.sub(r'mm+', '', output)
        output = re.sub(r' +', ' ', output)  # Collapse multiple spaces
        output = output.strip()
        
        # Discord has 2000 char limit per message
        if len(output) > 1900:
            output = output[:1900] + "\n\n... (truncated)"
        
        await message.remove_reaction('🤔', client.user)
        await message.add_reaction('✅')
        await message.reply(output)
        
    except subprocess.TimeoutExpired:
        await message.remove_reaction('🤔', client.user)
        await message.add_reaction('⏱️')
        await message.reply("⏱️ Query timed out after 2 minutes")
    except Exception as e:
        await message.remove_reaction('🤔', client.user)
        await message.add_reaction('❌')
        await message.reply(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in .env")
        exit(1)
    
    print("🚀 Starting Discord bot...")
    client.run(token)
