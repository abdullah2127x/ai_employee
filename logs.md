(ai-employee) PS D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor> python watchers/gmail_watcher_imap.py
Traceback (most recent call last):
  File "D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor\watchers\gmail_watcher_imap.py", line 21, in <module>
    class GmailWatcherIMAP(BaseWatcher):
    ...<288 lines>...
                self.mail = None
  File "D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor\watchers\gmail_watcher_imap.py", line 216, in GmailWatcherIMAP
    def _decode_body(self, msg: email.message.Message) -> str:
                                ^^^^^^^^^^^^^
AttributeError: module 'email' has no attribute 'message'
(ai-employee) PS D:\AbdullahQureshi\workspace\Hackathon-2025\GeneralAgentWithCursor> 
