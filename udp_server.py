import socket
import time
import json
import threading

# 默认配置，实际应从 json 读取
CONFIG = {
    "server_port": 10000,
    "timeout_seconds": 10  # 超过10秒没收到包视为断开
}

def load_config():
    try:
        with open("network.json", "r", encoding='utf-8') as f:
            data = json.load(f)
            CONFIG.update(data)
    except:
        pass

class UDPRelayServer:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', CONFIG["server_port"]))
        
        # 匹配队列: [addr1, addr2, ...]
        self.waiting_queue = [] 
        
        # 活跃房间: { player_addr: opponent_addr } (双向映射)
        self.sessions = {} 
        
        # 最后活跃时间: { addr: timestamp }
        self.last_active = {}
        
        print(f"UDP 中转服务器启动，监听 {CONFIG['server_port']}...")
        
        # 启动超时检测线程
        threading.Thread(target=self.check_timeouts, daemon=True).start()

    def check_timeouts(self):
        """定期检查所有玩家的心跳"""
        while True:
            time.sleep(2)
            now = time.time()
            timeout_limit = CONFIG["timeout_seconds"]
            
            # 找出超时的玩家
            timed_out_players = [addr for addr, last_time in self.last_active.items() 
                                 if now - last_time > timeout_limit]
            
            for addr in timed_out_players:
                print(f"玩家超时: {addr}")
                self.handle_disconnect(addr)

    def handle_disconnect(self, addr):
        """处理断开连接"""
        if addr in self.last_active:
            del self.last_active[addr]
            
        # 1. 如果在等待队列中，直接移除
        if addr in self.waiting_queue:
            self.waiting_queue.remove(addr)
            print(f"从队列移除: {addr}")
            
        # 2. 如果在游戏中，通知对手并拆除房间
        elif addr in self.sessions:
            opponent = self.sessions[addr]
            print(f"通知对手 {opponent} 对方已掉线")
            
            # 发送断开消息给对手
            try:
                disconnect_msg = json.dumps({"type": "OPPONENT_DISCONNECTED"}).encode()
                self.sock.sendto(disconnect_msg, opponent)
            except:
                pass
            
            # 清理双向映射
            if opponent in self.sessions: del self.sessions[opponent]
            if addr in self.sessions: del self.sessions[addr]
            
            # 对手也可能变成“无主”状态，可以选择将其放回队列或直接断开
            # 这里简单处理：让对手也进入断开流程（或者等待对手发心跳重建，但这比较复杂）
            # 最简单的逻辑是：一局游戏结束，双方都需要重新匹配

    def run(self):
        print("服务器主循环已启动...")
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                
                # 更新活跃时间
                self.last_active[addr] = time.time()
                
                # 尝试解析消息
                msg_obj = {}
                try:
                    if data.startswith(b"{"):
                        msg_obj = json.loads(data.decode())
                except:
                    pass

                # === 1. 心跳包处理 ===
                if msg_obj.get("type") == "HEARTBEAT":
                    # 如果已经在游戏中 (sesssions中)，且收到心跳，
                    # 可以在这里补发 GAME_START 以防丢包（可选优化），这里暂不实现以保持简洁
                    pass

                # === 2. 转发逻辑 (如果在游戏中) ===
                if addr in self.sessions:
                    target = self.sessions[addr]
                    # 直接转发原始数据
                    self.sock.sendto(data, target)
                
                # === 3. 匹配逻辑 (如果不在游戏中且不在队列中) ===
                elif addr not in self.waiting_queue:
                    print(f"新玩家加入匹配队列: {addr}")
                    self.waiting_queue.append(addr)
                    
                    # 检查队列是否满足匹配条件
                    if len(self.waiting_queue) >= 2:
                        self.match_players()

            except Exception as e:
                print(f"服务器错误: {e}")

    def match_players(self):
        """执行匹配并分配红蓝方"""
        p1 = self.waiting_queue.pop(0)
        p2 = self.waiting_queue.pop(0)
        
        # 建立双向会话映射
        self.sessions[p1] = p2
        self.sessions[p2] = p1
        print(f"匹配成功: {p1} <--> {p2}")

        # === 随机分配红蓝方 ===
        # True 代表 Host (Blue/先手), False 代表 Client (Red/后手)
        # random.choice 随机决定 p1 是先手还是后手
        p1_is_host = random.choice([True, False])
        p2_is_host = not p1_is_host

        # === 发送开始指令 ===
        # 构造 JSON 消息
        msg_p1 = json.dumps({"type": "GAME_START", "is_host": p1_is_host}).encode()
        msg_p2 = json.dumps({"type": "GAME_START", "is_host": p2_is_host}).encode()

        try:
            self.sock.sendto(msg_p1, p1)
            self.sock.sendto(msg_p2, p2)
            print(f"已下发身份: {p1}={'蓝方' if p1_is_host else '红方'}, {p2}={'蓝方' if p2_is_host else '红方'}")
        except Exception as e:
            print(f"下发身份失败: {e}")

if __name__ == "__main__":
    load_config()
    server = UDPRelayServer()
    server.run()