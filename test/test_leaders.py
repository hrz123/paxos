
import sys
import os.path
import heapq

from twisted.trial import unittest

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append( os.path.dirname(this_dir) )

from paxos.leaders import heartbeat


PVALUE = 99 # arbitrary value for proposal


class THBL (heartbeat.Proposer):
    
    hb_period       = 2
    liveness_window = 6
    
    def __init__(self):
        self.t = 1
        self.q = []
        self.cp     = 0
        self.hb     = 0
        self.pcount = 0
        self.hbcount = 0
        self.ap = 0
        self.acount = 0
        self.avalue = None
        self.tleader = None

        super(THBL,self).__init__(1, 3, PVALUE)


    def tadvance(self, incr=1):
        self.t += incr

        while self.q and self.q[0][0] <= self.t:
            heapq.heappop(self.q)[1]()

    def timestamp(self):
        return self.t

    def schedule(self, when, func_obj):
        whence = when + self.timestamp()
        heapq.heappush(self.q, (when + self.timestamp(), func_obj))


    def send_prepare(self, node_uid, pnum):
        self.cp = pnum
        self.pcount += 1

    def send_heartbeat(self, node_uid, pnum):
        self.hb = pnum
        self.hbcount += 1

    def send_accept(self, node_uid, pnum, value):
        self.ap = pnum
        self.acount += 1
        self.avalue = value

    def on_leadership_acquired(self):
        self.tleader = 'gained'

    def on_leadership_lost(self):
        self.tleader = 'lost'
        

        
class HeartbeatProposerTester (unittest.TestCase):

    
    def setUp(self):
        self.l = THBL()

        
    def p(self):
        self.l.tadvance(1)
        self.l.poll_liveness()

        
    def test_initial_wait(self):
        for i in range(1,7):
            self.p()
            self.assertEquals( self.l._acquiring, None )
            
        self.p()
        self.assertEquals( self.l._acquiring, 1 )


    def test_initial_leader(self):
        self.l.leader_uid = 2
        
        for i in range(1,7):
            self.p()
            self.assertEquals( self.l._acquiring, None )

        self.l.recv_heartbeat( 2, 1 )
        
        self.p()
        self.assertEquals( self.l._acquiring, None )

        
    def test_gain_leader(self):
        for i in range(1,7):
            self.p()


        self.assertEquals( self.l.pcount, 0 )
        self.assertEquals( self.l.cp,     0 )
        self.p()
        self.assertEquals( self.l.pcount, 1 )
        self.assertEquals( self.l.cp,     1 )

        self.assertEquals(self.l.recv_promise(2, 1, None, None), None)
        self.assertEquals(self.l.recv_promise(3, 1, None, None), None)
        self.assertEquals(self.l.recv_promise(4, 1, None, None), (1, PVALUE))

        self.assertEquals( self.l.tleader, 'gained' )


    def test_leader_acquire_rejected(self):
        for i in range(1,7):
            self.p()


        self.assertEquals( self.l.pcount, 0 )
        self.assertEquals( self.l.cp,     0 )
        self.p()
        self.assertEquals( self.l.pcount, 1 )
        self.assertEquals( self.l.cp,     1 )

        self.assertEquals(self.l.recv_promise(2, 1, None, None), None)
        self.assertEquals(self.l.recv_promise(3, 1, None, None), None)

        self.l.recv_proposal_rejected(2, 5)
        
        self.assertEquals(self.l.recv_promise(4, 1, None, None), (1, PVALUE))

        self.assertEquals( self.l.tleader, None )


    def test_ignore_old_leader_acquire_rejected(self):
        for i in range(1,7):
            self.p()

        self.assertEquals( self.l.pcount, 0 )
        self.assertEquals( self.l.cp,     0 )
        self.p()
        self.assertEquals( self.l.pcount, 1 )
        self.assertEquals( self.l.cp,     1 )

        self.assertEquals(self.l.recv_promise(2, 1, None, None), None)
        self.assertEquals(self.l.recv_promise(3, 1, None, None), None)

        self.l.recv_proposal_rejected(2, 0)
        
        self.assertEquals(self.l.recv_promise(4, 1, None, None), (1, PVALUE))

        self.assertEquals( self.l.tleader, 'gained' )


    def test_lose_leader(self):
        self.test_gain_leader()

        self.assertEquals( self.l.leader_uid, 1 )
        
        self.l.recv_heartbeat( 2, 5 )

        self.assertEquals( self.l.leader_uid, 2 )
        self.assertEquals( self.l.tleader, 'lost' )


    def test_regain_leader(self):
        self.test_lose_leader()

        for i in range(1, 7):
            self.p()

        self.assertEquals( self.l.pcount, 1 )
        self.assertEquals( self.l.cp,     1 )
        self.p()
        self.assertEquals( self.l.pcount, 2 )
        self.assertEquals( self.l.cp,     6 )

        self.assertEquals(self.l.recv_promise(2, 6, None, None), None)
        self.assertEquals(self.l.recv_promise(3, 6, None, None), None)
        self.assertEquals(self.l.recv_promise(4, 6, None, None), (6, PVALUE))

        self.assertEquals( self.l.tleader, 'gained' )
        
        

    def test_ignore_old_leader_heartbeat(self):
        self.test_lose_leader()

        self.l.recv_heartbeat( 1, 1 )

        self.assertEquals( self.l.leader_uid, 2 )


    def test_pulse(self):
        self.test_gain_leader()

        for i in range(0,8):
            self.l.tadvance()

        self.assertEquals( self.l.hbcount, 5 )
        self.assertEquals( self.l.leader_uid, 1 )
        self.assertTrue( self.l.leader_is_alive() )


    def test_leader_acquire_timeout_and_retry(self):
        for i in range(1,7):
            self.p()

        self.assertEquals( self.l.pcount, 0 )
        self.assertEquals( self.l.cp,     0 )
        self.p()
        self.assertEquals( self.l.pcount, 1 )
        self.assertEquals( self.l.cp,     1 )

        self.assertEquals(self.l.recv_promise(2, 1, None, None), None)
        self.assertEquals(self.l.recv_promise(3, 1, None, None), None)

        for i in range(0,6):
            self.assertEquals( self.l.pcount, 1 )
            self.assertEquals( self.l.cp,     1 )

        self.p()

        self.assertEquals( self.l.pcount, 2 )
        self.assertEquals( self.l.cp,     1 )

        self.assertEquals(self.l.recv_promise(4, 1, None, None), (1, PVALUE))

        self.assertEquals( self.l.tleader, 'gained' )
        
            

        
