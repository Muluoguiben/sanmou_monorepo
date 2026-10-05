"""Independent CR01-CR03 repair acceptance; synthetic data only."""
import asyncio
import unittest
from adversarial import ReviewNegatives
from test_task_runner import runner, SequenceClient
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_contracts import PolicyDecision

class InterruptStore(MemoryRunStore):
    def __init__(self, phase, action):
        super().__init__()
        self.phase, self.action = phase, action
        self.owner = None
        self.fired = False
    def save(self, state):
        super().save(state)
        pending = state.pending_call or ''
        match = pending == 'session_status' if self.phase == 'tool' else pending.startswith('policy:')
        if match and not self.fired:
            self.fired = True
            getattr(self.owner, self.action)()

class SpyPolicy:
    policy_id = 'cr-model-accounting'
    uses_model = True
    def __init__(self, result=None, error=None):
        self.calls = 0
        self.result = result or PolicyDecision(action='continue', reason='synthetic')
        self.error = error
    async def decide(self, context):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result

class RepairAcceptance(unittest.IsolatedAsyncioTestCase):
    async def test_checkpoint_interrupts_tool_and_policy_preserve_accounting(self):
        for phase in ('tool', 'policy'):
            for action in ('cancel', 'pause'):
                with self.subTest(phase=phase, action=action):
                    store = InterruptStore(phase, action)
                    client, policy = SequenceClient(), SpyPolicy()
                    r = runner(client, policy=policy, store=store)
                    store.owner = r
                    result = await r.run()
                    self.assertTrue(store.fired)
                    self.assertEqual(result.status, 'cancelled' if action == 'cancel' else 'paused')
                    self.assertEqual(policy.calls, 0)
                    if phase == 'tool':
                        self.assertEqual(client.calls, [])
                    self.assertEqual(result.completed_steps, 0)
                    self.assertEqual(r.budget.summary()['pending'], 0)
                    self.assertEqual(r.budget.summary()['counts']['step'], 1)
                    self.assertEqual(r.budget.summary()['counts']['model'], int(phase == 'policy'))
                    before = list(client.calls)
                    result_again = await r.run()
                    self.assertEqual(result_again.status, result.status)
                    self.assertEqual(client.calls, before)
                    if action == 'cancel':
                        restarted = runner(SequenceClient(count=client.count), store=store)
                        self.assertEqual((await restarted.run(resume=True)).status, 'cancelled')
                        self.assertEqual(restarted._client.calls, [])
                    else:
                        prior_ids = list(r.state.observation_ids)
                        resumed = await r.run(resume=True)
                        self.assertEqual(resumed.status, 'succeeded')
                        self.assertEqual(len(resumed.observation_ids), len(set(resumed.observation_ids)))
                        self.assertEqual(resumed.observation_ids[:len(prior_ids)], prior_ids)

    async def test_model_transport_contract_business_layers_and_unknown_usage(self):
        cases = [
            ('connection', ConnectionError('synthetic'), None, 'error', 'not_checked'),
            ('timeout', TimeoutError('synthetic'), None, 'error', 'not_checked'),
            ('cancel', asyncio.CancelledError(), None, 'cancelled', 'not_checked'),
            ('malformed', None, {'action':'succeed','reason':'bad','executable':True}, 'ok', 'error'),
            ('stop', None, PolicyDecision(action='stop',reason='bounded'), 'ok', 'ok'),
        ]
        for label, error, returned, transport, contract in cases:
            with self.subTest(label=label):
                policy = SpyPolicy(result=returned, error=error)
                r = runner(policy=policy)
                if label == 'cancel':
                    with self.assertRaises(asyncio.CancelledError):
                        await r.run()
                    self.assertEqual(r.state.status, 'cancelled')
                else:
                    await r.run()
                event = next(e for e in r.trace.events if e.event == 'policy')
                self.assertEqual((event.transport, event.contract), (transport, contract))
                self.assertEqual(r.budget.summary()['counts']['model'], 1)
                self.assertEqual(r.budget.summary()['pending'], 0)
                self.assertIsNone(event.usage.input_tokens)
                self.assertIsNone(event.usage.cost)
                if label == 'stop':
                    self.assertEqual(event.business, 'stop')

    async def test_tool_schema_failure_is_not_transport_failure(self):
        def mutate(name, payload):
            if name == 'session_status':
                payload['execution_authority'] = 'live'
        r = runner(SequenceClient(mutate=mutate))
        result = await r.run()
        self.assertEqual(result.status, 'failed')
        event = next(e for e in r.trace.events if e.event == 'tool')
        self.assertEqual((event.transport, event.contract), ('ok', 'error'))
        self.assertEqual(r.budget.summary()['pending'], 0)
        self.assertFalse(r.harness.tool_log.records[0].success)

if __name__ == '__main__':
    unittest.main(verbosity=2)
