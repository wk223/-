# 文件名：analyzer.py
# 改造重点：parse()不再返回完整列表，直接流式写库，内存始终只占5万条

from config import FLUSH_SIZE
from scapy.all import PcapReader, IP, TCP, UDP, ICMP, ARP, DNS
from database import db
import pandas as pd

# 每批写入数据库的包数量，平衡内存和写入频率



class PcapAnalyzer:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def parse_and_save(self, task_id: str) -> int:
        """
        流式读取pcap，每FLUSH_SIZE条直接写库，不在内存积累。
        返回总解析包数。
        改造前：全部解析完再返回列表 → 百万包全在内存
        改造后：边解析边写库 → 内存永远只有5万条
        """
        buffer = []
        total = 0
        engine = db.engine

        with PcapReader(self.filepath) as reader:
            for i, pkt in enumerate(reader):
                rec = self._parse_one(pkt, i)
                rec['task_id'] = task_id
                buffer.append(rec)

                # 攒够一批就写库，清空buffer
                if len(buffer) >= FLUSH_SIZE:
                    self._flush_to_db(buffer, engine)
                    total += len(buffer)
                    buffer = []
                    print(f"[进度] task={task_id} 已写入 {total} 包")

        # 写入最后一批剩余的
        if buffer:
            self._flush_to_db(buffer, engine)
            total += len(buffer)

        print(f"[完成] task={task_id} 共写入 {total} 包")
        return total

    def _flush_to_db(self, records: list, engine):
        """批量写入数据库"""
        if not records:
            return

        import pandas as pd
        df = pd.DataFrame(records)

        # 用pandas to_sql写入，兼容SQLAlchemy 2.x
        df.to_sql(
            'traffic',
            engine,
            if_exists='append',
            index=False,
            chunksize=5000
        )

    def _parse_one(self, pkt, i: int) -> dict:
        """解析单个数据包，返回字典"""
        rec = {
            'index': i,
            'timestamp': float(pkt.time),
            'length': len(pkt),
            'protocol': 'OTHER',
            'src_ip': None, 'dst_ip': None,
            'src_port': None, 'dst_port': None,
            'flags': None, 'info': '',
        }
        if pkt.haslayer(IP):
            rec['src_ip'] = pkt[IP].src
            rec['dst_ip'] = pkt[IP].dst

        if pkt.haslayer(TCP):
            rec['protocol'] = 'TCP'
            rec['src_port'] = pkt[TCP].sport
            rec['dst_port'] = pkt[TCP].dport
            rec['flags'] = str(pkt[TCP].flags)
            rec['info'] = {80: 'HTTP', 443: 'HTTPS', 22: 'SSH',
                           23: 'Telnet', 21: 'FTP'}.get(pkt[TCP].dport, '')
        elif pkt.haslayer(UDP):
            rec['protocol'] = 'UDP'
            rec['src_port'] = pkt[UDP].sport
            rec['dst_port'] = pkt[UDP].dport
            if pkt.haslayer(DNS):
                rec['info'] = 'DNS'
        elif pkt.haslayer(ICMP):
            rec['protocol'] = 'ICMP'
        elif pkt.haslayer(ARP):
            rec['protocol'] = 'ARP'
            rec['src_ip'] = pkt[ARP].psrc
            rec['dst_ip'] = pkt[ARP].pdst

        return rec