import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from receivers.TelegramReceiver import TelegramReceiver

if __name__ == "__main__":
    receiver = TelegramReceiver()
    receiver.run()
