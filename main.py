import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.DAO import DAO
from core.Processer import Processer
from ia.gemini import GeminiExtractor
from receivers.TelegramReceiver import TelegramReceiver

if __name__ == "__main__":
    dao = DAO()
    extractor = GeminiExtractor()
    processer = Processer(extractor, dao)
    receiver = TelegramReceiver(processer)
    receiver.run()
