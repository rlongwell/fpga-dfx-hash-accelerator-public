"""Regressions for wrapped command echoes seen on the physical UART."""
import importlib.util
import base64
import gzip
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('compare_inputs',Path(__file__).resolve().parents[1]/'compare_inputs.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SerialRecords(unittest.TestCase):
    def test_job_id_ignores_wrapped_echo(self):
        transcript="nohup python3 ... & echo\r\r\nJOB_PID:$!; printf '\\nDEMO_CMD_83f2fd9d_%s\\n' \"$?\"\r\nJOB_PID:1234\r\n\r\n"
        self.assertEqual(module.marker_value(transcript,'JOB_PID',r'\d+'),'1234')

    def test_wait_is_not_a_completed_job(self):
        transcript='JOB_RC:"; cat /root/job.status; else echo JOB_WAIT; fi\r\nJOB_WAIT\r\n'
        self.assertIsNone(module.marker_value(transcript,'JOB_RC',r'-?\d+',required=False))

    def test_zero_and_negative_return_codes(self):
        for value in ('0','-15'):
            self.assertEqual(module.marker_value('JOB_RC:'+value+'\r\n','JOB_RC',r'-?\d+'),value)

    def test_missing_or_ambiguous_record_fails(self):
        for text in ('JOB_PID:$!\r\n','JOB_PID:1\nJOB_PID:2\n'):
            with self.assertRaises(ValueError):module.marker_value(text,'JOB_PID',r'\d+')

    def test_interleaved_console_message_retries_read_only(self):
        payload=b'{"ok":true,"digest":"verified physical result"}\n'
        encoded=base64.b64encode(gzip.compress(payload)).decode()
        valid='LOG_PAYLOAD:'+encoded+'\r\n'
        damaged='LOG_PAYLOAD:'+encoded[:20]+'[123] macb eth0: Link is Up\n'+encoded[20:]+'\r\n'
        command=Mock(side_effect=[damaged,valid])
        with patch.object(module.time,'sleep'):
            self.assertEqual(module.read_log_payload(command,'/root/test.log'),payload)
        self.assertEqual(command.call_count,2)
        self.assertEqual(command.call_args_list[0],command.call_args_list[1])
        self.assertIn('"rb"',command.call_args[0][0])

    def test_invalid_gzip_crc_is_not_accepted(self):
        payload=b'physical evidence\n'
        packed=bytearray(gzip.compress(payload));packed[-8]^=1
        command=Mock(side_effect=['LOG_PAYLOAD:'+base64.b64encode(packed).decode(),
                                 'LOG_PAYLOAD:'+base64.b64encode(gzip.compress(payload)).decode()])
        with patch.object(module.time,'sleep'):
            self.assertEqual(module.read_log_payload(command,'/root/test.log'),payload)
        self.assertEqual(command.call_count,2)

    def test_retries_are_bounded_and_ambiguous_records_rejected(self):
        valid='LOG_PAYLOAD:'+base64.b64encode(gzip.compress(b'data')).decode()+'\n'
        command=Mock(return_value=valid+valid)
        with patch.object(module.time,'sleep'),self.assertRaises(ValueError):
            module.read_log_payload(command,'/root/test.log')
        self.assertEqual(command.call_count,3)


if __name__=='__main__':unittest.main()
