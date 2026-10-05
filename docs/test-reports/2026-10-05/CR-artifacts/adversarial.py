import asyncio
import unittest
from test_task_runner import runner, SequenceClient
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_contracts import PolicyDecision

class ScheduledInterruptStore(MemoryRunStore):
    def __init__(self, action):
        super().__init__()
        self.action = action
        self.owner = None
        self.armed = True
        self.seen = []
    def save(self, state):
        super().save(state)
        self.seen.append(state.pending_call)
        if self.armed and state.pending_call == 'session_status':
            self.armed = False
            getattr(self.owner, self.action)()

class ReviewNegatives(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_during_checkpoint_before_client_dispatch(self):
        store = ScheduledInterruptStore('cancel')
        client = SequenceClient()
        r = runner(client, store=store)
        store.owner = r
        result = await r.run()
        print('INTERRUPT', store.action, result.status, result.reason, client.calls)
        self.assertFalse(store.armed, str(store.seen))
        self.assertEqual(result.status, 'cancelled')
        self.assertEqual(client.calls, [], 'client dispatched after explicit cancellation')

    async def test_pause_during_checkpoint_before_client_dispatch(self):
        store = ScheduledInterruptStore('pause')
        client = SequenceClient()
        r = runner(client, store=store)
        store.owner = r
        result = await r.run()
        print('INTERRUPT', store.action, result.status, result.reason, client.calls)
        self.assertFalse(store.armed, str(store.seen))
        self.assertEqual(result.status, 'paused')
        self.assertEqual(client.calls, [], 'client dispatched after explicit pause')

    async def test_invalid_policy_response_has_successful_transport(self):
        class InvalidPolicy:
            policy_id = 'invalid-response'
            uses_model = False
            async def decide(self, context):
                return {'action':'succeed', 'reason':'invalid authority', 'executable':True}
        r = runner(policy=InvalidPolicy())
        await r.run()
        event = next(e for e in r.trace.events if e.event == 'policy')
        self.assertEqual((event.transport, event.contract), ('ok', 'error'))

    async def test_policy_transport_failure_does_not_claim_schema_check(self):
        class FailedPolicy:
            policy_id = 'failed-transport'
            uses_model = False
            async def decide(self, context):
                raise ConnectionError('synthetic transport failure')
        r = runner(policy=FailedPolicy())
        await r.run()
        event = next(e for e in r.trace.events if e.event == 'policy')
        self.assertEqual((event.transport, event.contract), ('error', 'not_checked'))

if __name__ == '__main__':
    unittest.main(verbosity=2)



