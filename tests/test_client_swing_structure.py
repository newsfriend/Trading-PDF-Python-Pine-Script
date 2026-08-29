import unittest

from python.client_swing_structure import ClientSwingStructure, LABELS, StructuralPivot


def pivots(prices):
    first_kind = -1 if prices[1] > prices[0] else 1
    return [
        StructuralPivot(bar=index * 4, price=price, kind=first_kind if index % 2 == 0 else -first_kind, atr=2.0, important_range=100.0)
        for index, price in enumerate(prices)
    ]


class ClientSwingStructureTests(unittest.TestCase):
    def test_bullish_impulse_then_abc_is_connected_and_archived(self):
        engine = ClientSwingStructure()
        series = pivots([100, 120, 110, 140, 125, 150, 132, 144, 126])
        completed = [engine.add(pivot) for pivot in series]
        self.assertTrue(completed[-1])
        self.assertEqual(len(engine.cycles), 1)
        self.assertEqual([node.price for node in engine.cycles[0]], [100, 120, 110, 140, 125, 150, 132, 144, 126])
        self.assertEqual(LABELS, ("0", "1", "2", "3", "4", "5", "A", "B", "C"))
        self.assertEqual(engine.nodes[0].price, 126)

    def test_bearish_impulse_then_abc_is_connected_and_archived(self):
        engine = ClientSwingStructure()
        series = pivots([150, 130, 140, 110, 125, 100, 118, 106, 124])
        for pivot in series:
            engine.add(pivot)
        self.assertEqual(len(engine.cycles), 1)
        self.assertEqual(engine.reason, "IMPULSE_AND_ABC_CONFIRMED")

    def test_wave2_origin_break_recounts_instead_of_printing_wave2(self):
        engine = ClientSwingStructure()
        for pivot in pivots([100, 120, 98]):
            engine.add(pivot)
        self.assertEqual(engine.reason, "W2_ORIGIN_BREAK_RECOUNT")
        self.assertEqual([node.price for node in engine.nodes], [98])

    def test_wave3_must_exceed_wave1_endpoint(self):
        engine = ClientSwingStructure()
        for pivot in pivots([100, 120, 110, 118]):
            engine.add(pivot)
        self.assertEqual(engine.reason, "W3_EXTENSION_PENDING")
        self.assertEqual(len(engine.nodes), 3)

    def test_revised_wave2_crossing_origin_forces_recount(self):
        engine = ClientSwingStructure()
        initial = pivots([100, 120, 110])
        for pivot in initial:
            engine.add(pivot)

        revised_wave2 = StructuralPivot(
            bar=16,
            price=98,
            kind=-1,
            atr=2.0,
            important_range=100.0,
        )
        engine.add(revised_wave2)

        self.assertEqual(engine.reason, "W2_ORIGIN_BREAK_RECOUNT")
        self.assertEqual(engine.nodes, [revised_wave2])

    def test_wave4_cannot_destroy_the_impulse_origin(self):
        engine = ClientSwingStructure()
        for pivot in pivots([100, 120, 110, 140, 99]):
            engine.add(pivot)
        self.assertEqual(engine.reason, "W4_ORIGIN_BREAK_RECOUNT")
        self.assertEqual([node.price for node in engine.nodes], [99])

    def test_xauusd_reference_scale_cycles_share_c_as_the_next_zero(self):
        """Mirror the connected repeated-cycle grammar in the client charts."""
        engine = ClientSwingStructure()
        prices = [
            3990, 4110, 4040, 4200, 4125, 4280, 4170, 4235, 4100,
            4400, 4300, 4620, 4480, 4700, 4560, 4640, 4450,
        ]
        kinds = [-1 if index % 2 == 0 else 1 for index in range(len(prices))]
        replay = [
            StructuralPivot(
                bar=index * 24,
                price=price,
                kind=kinds[index],
                atr=18.0,
                important_range=900.0,
            )
            for index, price in enumerate(prices)
        ]

        completed_at = [pivot.bar for pivot in replay if engine.add(pivot)]

        self.assertEqual(completed_at, [192, 384])
        self.assertEqual(len(engine.cycles), 2)
        self.assertEqual([node.price for node in engine.cycles[0]], prices[:9])
        self.assertEqual([node.price for node in engine.cycles[1]], prices[8:])
        self.assertEqual(engine.cycles[0][-1], engine.cycles[1][0])
        self.assertEqual(engine.nodes, [replay[-1]])
        self.assertEqual(LABELS, ("0", "1", "2", "3", "4", "5", "A", "B", "C"))


if __name__ == "__main__":
    unittest.main()
