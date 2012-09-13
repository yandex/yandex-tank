from Tank.Plugins.Aggregator import SecondAggregateData, AggregatorPlugin
import os
import logging
from Tests.TankTests import TankTestCase
from Tank.Plugins.Stepper import Stepper

class  StepperTestCase(TankTestCase):
    data = None
    
    def test_simple(self):
        stepper=Stepper()
        stepper.main()
