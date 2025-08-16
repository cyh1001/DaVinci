import os
from dotenv import load_dotenv
import virtuals_tweepy

load_dotenv()

def main():
    print("Hello from darwing-marketing!")
    
    # 获取API密钥
    api_key = os.getenv('TWITTER_API_KEY')
    
    if not api_key:
        print("请在.env文件中设置TWITTER_API_KEY")
        return
    
    try:
        # 使用virtuals-tweepy的Client
        client = virtuals_tweepy.Client(game_twitter_access_token =api_key)
        
        # 发送测试推特
        response = client.create_tweet(text="Hello from DarwinG-Marketing! 🚀 This is a test tweet.")
        
        if response.data:
            print(f"推特发送成功! Tweet ID: {response.data['id']}")
            print(f"Tweet URL: https://twitter.com/user/status/{response.data['id']}")
        else:
            print("推特发送失败")
            
    except Exception as e:
        print(f"发送推特时出错: {e}")
        print("提示：确保你的API密钥是有效的Twitter Bearer Token")


if __name__ == "__main__":
    main()
