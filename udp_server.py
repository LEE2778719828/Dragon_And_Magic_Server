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
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                
                # 更新心跳
                self.last_active[addr] = time.time()
                
                # 解析消息类型（如果是JSON）
                msg_type = ""
                try:
                    if data.startswith(b"{"):
                        msg_obj = json.loads(data.decode())
                        msg_type = msg_obj.get("type")
                except:
                    pass

                # === 逻辑 1: 心跳包 ===
                if msg_type == "HEARTBEAT":
                    # 仅更新时间，不做转发
                    continue

                # === 逻辑 2: 匹配/转发 ===
                if addr in self.sessions:
                    # 已在房间中，直接转发
                    target = self.sessions[addr]
                    self.sock.sendto(data, target)
                
                elif addr not in self.waiting_queue:
                    # 新玩家，加入队列
                    print(f"新玩家进入队列: {addr}")
                    self.waiting_queue.append(addr)
                    
                    # 尝试匹配
                    if len(self.waiting_queue) >= 2:
                        p1 = self.waiting_queue.pop(0)
                        p2 = self.waiting_queue.pop(0)
                        
                        # 建立双向映射
                        self.sessions[p1] = p2
                        self.sessions[p2] = p1
                        print(f"匹配成功: {p1} <--> {p2}")
                        
                        # 可选：通知双方匹配成功（BattleApp的握手会处理，这里只需打通）

            except Exception as e:
                print(f"服务器错误: {e}")

if __name__ == "__main__":
    load_config()
    server = UDPRelayServer()
    server.run()