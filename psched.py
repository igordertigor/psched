from tqdm import trange
from datetime import datetime, timedelta
from jinja2 import Template
import numpy as np

DEFAULT_TEMPLATE = Template(
    '{{ start }}-{{ end }} : {{ name }} '
    '{% if stakeholders %}({{ stakeholders }}){% endif %}')


class Time(object):

    def __init__(self, hour, minute=None):
        if isinstance(hour, str):
            hour, minute = [int(x) for x in hour.split(':')]
        self.t = datetime(2019, 1, 1, hour, minute)

    def __iadd__(self, minutes):
        self.t += timedelta(minutes=minutes)
        return self

    def __add__(self, minutes):
        t = Time(self.t.hour, self.t.minute)
        t += minutes
        return t

    def __lt__(self, t):
        return self.t < t.t

    def __gt__(self, t):
        return self.t > t.t

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return self.t.strftime('%H:%M')


T0 = Time('9:30')


class WaitTimeCounter(object):

    def __init__(self, observed, constraints):
        self.observed = list(observed)
        self.constraints = constraints
        self.active = False
        self.total_time = 0.

    def append(self, name, duration, t):
        if name in self.observed:
            self.active = True
            i = self.observed.index(name)
            self.observed.pop(i)
        if self.active:
            self.total_time += duration
            violations = sum([f(t) for f in self.constraints])
        else:
            violations = 0
        if len(self.observed) == 0:
            self.active = False
        return violations


class Events(object):

    def __init__(self, events, break_every=5, lunch_after=10):
        self.events = list(events)
        self.break_every = break_every
        self.lunch_after = lunch_after
        self.lunch_duration = 60
        self.break_duration = 15

    def __len__(self):
        return len(self.events)

    def iterate(self, order):
        i, k = 0, 0
        for idx in order:
            yield list(self.events[idx]) + [15]
            i += 1
            k += 1
            if k == self.lunch_after:
                yield ('Lunch', [], self.lunch_duration)
                i, k = 0, 0
            elif i == self.break_every:
                yield ('Break', [], self.break_duration)


class Schedule(object):

    def __init__(self,
                 events,
                 stakeholders=None,
                 t0=T0,
                 generation_size=100):
        self.n = generation_size
        self.t0 = t0
        self.events = events
        self.stakeholders = stakeholders
        self.order = np.stack([np.random.permutation(len(events))
                               for _ in range(self.n)], 0)
        self.refresh()

    def score(self, order):
        wait_times, violations = self.individual_wait_times(order)
        return (1000*violations +
                sum(wait_times.values()))

    def individual_wait_times(self, order=None):
        if order is None:
            order = self.order[0]
        wait_times = {name: WaitTimeCounter(*self.stakeholders[name])
                      for name in self.stakeholders}
        t = self.t0
        violations = 0.
        for event, constraints, duration in self.events.iterate(order):
            for constraint in constraints:
                violations += constraint(t)
            for name in self.stakeholders:
                violations += wait_times[name].append(event, duration, t)
            t = t + duration
        return (
            {name: counter.total_time for name, counter in wait_times.items()},
            violations)

    def refresh(self):
        self.scores = np.array([self.score(o) for o in self.order])
        self.order, self.scores = self.sort_by_rank(self.order, self.scores)

    def compete(self, nbest=4, pswap=0.8):
        new_order = []
        for _ in range(self.n):
            idx = np.random.randint(nbest)
            order = self.order[idx].copy()
            if np.random.rand() < pswap:
                i, j = np.random.randint(self.order.shape[1], size=2)
                order[i], order[j] = order[j], order[i]
            new_order.append(order)
        self.order = np.array(new_order)
        self.refresh()

    def optimize(self, ngenerations):
        with trange(ngenerations) as generations:
            generations.set_description('Generating')
            for _ in generations:
                self.compete()
                generations.set_postfix(
                    best=self.scores.min(),
                    mean='{:.3f}'.format(self.scores.mean()))

    @staticmethod
    def sort_by_rank(orders, scores):
        i = np.argsort(scores)
        return orders[i], scores[i]

    def render(self, idx=0, template=DEFAULT_TEMPLATE):
        t0 = self.t0
        order = self.order[idx]
        s = []
        for event, _, duration in self.events.iterate(order):
            stakeholders = [name
                            for name, (focus, _) in self.stakeholders.items()
                            if event in focus]
            if len(stakeholders):
                stakeholders = ', '.join(stakeholders)
            else:
                stakeholders = ''
            t1 = t0 + duration
            s.append(template.render(start=t0,
                                     end=t1,
                                     name=event,
                                     stakeholders=stakeholders))
            t0 = t1
        return '\n'.join(s)


def not_before(time):
    t = Time(time)

    def checker(x):
        return x < t

    return checker


def not_after(time):
    t = Time(time)

    def checker(x):
        return x > t

    return checker


if __name__ == '__main__':
    events = [('Torsten Hansen', []),
              ('Matthias Schmidt', [not_after('11:00')]),
              ('Anna Popanna', []),
              ('Dela Obutu', []),
              ('Tara Dezhdar', []),
              ('Ingo Fruend', []),
              ('Juliane Meyer', []),
              ('Joe Fresh', []),
              ('Tatjana Danilova', []),
              ('Coolio', []),
              ('Kurt (ohne Helm und ohne Gurt)', []),
              ('Heinz-Christian Fruend', []),
              ]
    stakeholders = {'Otto von Bismark':
                    ({'Torsten Hansen', 'Matthias Schmidt', 'Anna Popanna',
                      'Kurt (ohne Helm und ohne Gurt)'},
                     [not_before('10:00'),
                      not_after('13:00')]),
                    'Hannelore Elsner':
                    ({'Anna Popanna', 'Dela Obutu', 'Torsten Hansen',
                      'Joe Fresh', 'Coolio'},
                     []),
                    'Franz von Assisi':
                    ({'Dela Obutu', 'Tara Dezhdar', 'Ingo Fruend', 'Coolio',
                      'Heinz-Christian Fruend'},
                     [not_after('13:00')]),
                    'Nathan der Weise':
                    ({'Ingo Fruend', 'Juliane Meyer', 'Joe Fresh',
                      'Tatjana Danilova', 'Kurt (ohne Helm und ohne Gurt)'},
                     [not_before('10:30')]),
                    }

    sched = Schedule(
        Events(events),
        stakeholders)
    sched.optimize(200)

    # print(sched.render(template=Template(
    #     r'{{ start }} -- {{ end }} & {{ name }} & {{ stakeholders }}\\')))
    print(sched.render())
    print(sched.individual_wait_times())
