import time
import unittest
from unittest.mock import patch
import bridge


class ControlTests(unittest.TestCase):
    def test_hysteresis_and_limits(self):
        self.assertEqual(bridge.compute_duty(23, 23.1, 'auto', 65, False, False), (0, False))
        self.assertEqual(bridge.compute_duty(23, 22, 'auto', 65, False, False), (40, True))
        self.assertEqual(bridge.compute_duty(23, 23.4, 'auto', 65, False, True), (0, False))
        for mode in ('auto', 'manual'):
            self.assertEqual(bridge.compute_duty(30, 30, mode, 100, False, True), (0, False))
        self.assertEqual(bridge.compute_duty(23, 18, 'manual', 55, False, False), (55, False))
        self.assertEqual(bridge.compute_duty(23, 18, 'off', 55, False, True), (0, False))
        self.assertEqual(bridge.compute_duty(23, 18, 'auto', 55, True, True), (0, False))

    def test_invalid_inputs(self):
        for data in ({'target':float('nan')}, {'target':31}, {'target':True}, {'manual':0}, {'paused':'false'}, {'mode':'cool'}, []):
            with self.assertRaises(ValueError):
                bridge.validate_control(data)

    @patch.object(bridge, 'TOKEN', 'test')
    @patch.object(bridge, 'SENSOR', 'http://sensor')
    def test_live_and_sensor_failure(self):
        c = bridge.Controller()
        c.state['mode'] = 'auto'
        c.last_client = time.monotonic()
        def fake(url, body=None, token=None):
            if url == bridge.SENSOR:
                return {'temperature':21}
            if url.endswith('/json_rpc'):
                return {'result':{'status':'OK'}}
            return {'hashrate':{'total':[4500]}}
        with patch.object(bridge, 'request_json', side_effect=fake):
            c.tick()
        self.assertEqual(c.state['duty'],80)
        self.assertIsNone(c.state['error'])
        with patch.object(bridge, 'request_json', side_effect=[{'temperature':float('nan')}, {'result':{}}]) as req:
            c.tick()
            self.assertEqual(req.call_args.args[1]['method'],'pause')
        self.assertEqual(c.state['duty'],0)
        self.assertFalse(c.state['heating'])

    @patch.object(bridge, 'TOKEN', 'test')
    @patch.object(bridge, 'SENSOR', 'http://sensor')
    def test_browser_timeout_and_stale_sensor(self):
        c = bridge.Controller()
        c.state['mode']='manual'
        with patch.object(bridge, 'request_json', side_effect=[{'temperature':21},{'result':{}},{'hashrate':{'total':[0]}}]) as req:
            c.tick()
            self.assertTrue(c.state['paused'])
            self.assertEqual(req.call_args_list[1].args[1]['method'],'pause')
        with patch.object(bridge, 'request_json', side_effect=[{'temperature':21,'timestamp':time.time()-60},{'result':{}}]):
            c.tick()
        self.assertIn('stale',c.state['error'])

    def test_pause_command_immediate(self):
        c=bridge.Controller()
        with patch.object(bridge, 'request_json', return_value={'result':{}}) as req:
            c.control({'paused':True})
            self.assertEqual(req.call_args.args[1]['method'],'pause')

if __name__ == '__main__':
    unittest.main()
