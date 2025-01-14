import selectors
import unittest
from unittest.mock import Mock, patch

import context

from tn3270.telnet import Telnet

class OpenTestCase(unittest.TestCase):
    def setUp(self):
        self.socket_mock = Mock()

        self.socket_selector_mock = Mock()

        selector_key = Mock(fileobj=self.socket_mock)

        self.socket_selector_mock.select.return_value = [(selector_key, selectors.EVENT_READ)]

        patcher = patch('socket.create_connection')

        create_connection_mock = patcher.start()

        create_connection_mock.return_value = self.socket_mock

        patcher = patch('selectors.DefaultSelector')

        default_selector_mock = patcher.start()

        default_selector_mock.return_value = self.socket_selector_mock

        self.addCleanup(patch.stopall)

    def test_basic_tn3270_negotiation(self):
        # Arrange
        self.telnet = Telnet('IBM-3279-2-E')

        responses = [
            bytes.fromhex('ff fd 18'),
            bytes.fromhex('ff fa 18 01 ff f0'),
            bytes.fromhex('ff fd 19'),
            bytes.fromhex('ff fb 19'),
            bytes.fromhex('ff fd 00'),
            bytes.fromhex('ff fb 00')
        ]

        self.socket_mock.recv = Mock(side_effect=responses)

        self.assertFalse(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        # Act
        self.telnet.open('mainframe', 23)

        # Assert
        self.assertTrue(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 18'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fa 18 00 49 42 4d 2d 33 32 37 39 2d 32 2d 45 ff f0'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 19'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fd 19'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 00'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fd 00'))

    def test_tn3270e_negotiation(self):
        # Arrange
        self.telnet = Telnet('IBM-3279-2-E')

        responses = [
            bytes.fromhex('ff fd 28'),
            bytes.fromhex('ff fa 28 08 02 ff f0'),
            bytes.fromhex('ff fa 28 02 04 49 42 4d 2d 33 32 37 38 2d 32 2d 45 01 54 43 50 30 30 30 33 34 ff f0'),
            bytes.fromhex('ff fa 28 03 04 ff f0')
        ]

        self.socket_mock.recv = Mock(side_effect=responses)

        self.assertFalse(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        # Act
        self.telnet.open('mainframe', 23)

        # Assert
        self.assertTrue(self.telnet.is_tn3270_negotiated)
        self.assertTrue(self.telnet.is_tn3270e_negotiated)

        self.assertEqual(self.telnet.device_type, 'IBM-3278-2-E')
        self.assertEqual(self.telnet.device_name, 'TCP00034')

        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 28'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fa 28 02 07 49 42 4d 2d 33 32 37 38 2d 32 2d 45 ff f0'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fa 28 03 07 ff f0'))

    def test_basic_tn3270_negotiation_when_tn3270e_not_enabled(self):
        # Arrange
        self.telnet = Telnet('IBM-3279-2-E', is_tn3270e_enabled=False)

        responses = [
            bytes.fromhex('ff fd 28'),
            bytes.fromhex('ff fd 18'),
            bytes.fromhex('ff fa 18 01 ff f0'),
            bytes.fromhex('ff fd 19'),
            bytes.fromhex('ff fb 19'),
            bytes.fromhex('ff fd 00'),
            bytes.fromhex('ff fb 00')
        ]

        self.socket_mock.recv = Mock(side_effect=responses)

        self.assertFalse(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        # Act
        self.telnet.open('mainframe', 23)

        # Assert
        self.assertTrue(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fc 28'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 18'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fa 18 00 49 42 4d 2d 33 32 37 39 2d 32 2d 45 ff f0'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 19'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fd 19'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fb 00'))
        self.socket_mock.sendall.assert_any_call(bytes.fromhex('ff fd 00'))

    def test_unsuccessful_negotiation(self):
        # Arrange
        self.telnet = Telnet('IBM-3279-2-E')

        self.socket_mock.recv = Mock(return_value='hello world'.encode('ascii'))

        self.assertFalse(self.telnet.is_tn3270_negotiated)
        self.assertFalse(self.telnet.is_tn3270e_negotiated)

        # Act and assert
        with self.assertRaisesRegex(Exception, 'Unable to negotiate TN3270 mode'):
            self.telnet.open('mainframe', 23)

class ReadMultipleTestCase(unittest.TestCase):
    def setUp(self):
        self.telnet = Telnet('IBM-3279-2-E')

        self.telnet.socket = Mock()

        self.telnet.socket_selector = Mock()

        self.is_tn3270e_negotiated = False

        selector_key = Mock(fileobj=self.telnet.socket)

        self.telnet.socket_selector.select.return_value = [(selector_key, selectors.EVENT_READ)]

        self.addCleanup(patch.stopall)

    def test_multiple_records_in_single_recv(self):
        # Arrange
        self.telnet.socket.recv = Mock(return_value=bytes.fromhex('01 02 03 ff ef 04 05 06 ff ef'))

        # Act and assert
        self.assertEqual(self.telnet.read_multiple(), [bytes.fromhex('01 02 03'), bytes.fromhex('04 05 06')])

    def test_single_record_spans_multiple_recv(self):
        # Arrange
        self.telnet.socket.recv = Mock(side_effect=[bytes.fromhex('01 02 03'), bytes.fromhex('04 05 06 ff ef')])

        # Act and assert
        self.assertEqual(self.telnet.read_multiple(), [bytes.fromhex('01 02 03 04 05 06')])

    def test_limit(self):
        # Arrange
        self.telnet.socket.recv = Mock(return_value=bytes.fromhex('01 02 03 ff ef 04 05 06 ff ef'))

        # Act and assert
        self.assertEqual(self.telnet.read_multiple(limit=1), [bytes.fromhex('01 02 03')])

    def test_timeout(self):
        # Arrange
        self.telnet.socket.recv = Mock(side_effect=[bytes.fromhex('01 02 03')])

        selector_key = Mock(fileobj=self.telnet.socket)

        self.telnet.socket_selector.select.side_effect = [[(selector_key, selectors.EVENT_READ)], []]

        # Act and assert
        with patch('time.perf_counter') as perf_counter_mock:
            perf_counter_mock.side_effect=[1, 3, 3, 7]

            self.telnet.read_multiple(timeout=5)

            self.assertEqual(self.telnet.socket_selector.select.call_count, 2)

            mock_calls = self.telnet.socket_selector.select.mock_calls

            self.assertEqual(mock_calls[0][1][0], 5)
            self.assertEqual(mock_calls[1][1][0], 3)

    def test_recv_eof(self):
        # Arrange
        self.telnet.socket.recv = Mock(return_value=b'')

        self.assertFalse(self.telnet.eof)

        # Act and assert
        with self.assertRaises(EOFError):
            self.telnet.read_multiple()

        self.assertTrue(self.telnet.eof)

    def test_tn3270e(self):
        # Arrange
        self.telnet.is_tn3270e_negotiated = True

        self.telnet.socket.recv = Mock(return_value=bytes.fromhex('00 00 00 00 00 01 02 03 ff ef'))

        # Act and assert
        self.assertEqual(self.telnet.read_multiple(), [bytes.fromhex('01 02 03')])

class WriteTestCase(unittest.TestCase):
    def test_basic_tn3270(self):
        # Arrange
        telnet = Telnet('IBM-3279-2-E')

        telnet.socket = Mock()

        telnet.is_tn3270e_negotiated = False

        # Act
        telnet.write(bytes.fromhex('01 02 03 ff 04 05'))

        # Assert
        telnet.socket.sendall.assert_called_with(bytes.fromhex('01 02 03 ff ff 04 05 ff ef'))

    def test_tn3270e(self):
        # Arrange
        telnet = Telnet('IBM-3279-2-E')

        telnet.socket = Mock()

        telnet.is_tn3270e_negotiated = True

        # Act
        telnet.write(bytes.fromhex('01 02 03 ff 04 05'))

        # Assert
        telnet.socket.sendall.assert_called_with(bytes.fromhex('00 00 00 00 00 01 02 03 ff ff 04 05 ff ef'))
