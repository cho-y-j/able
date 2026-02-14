"""Genetic Algorithm optimizer for trading strategy parameters.

Uses a simple evolutionary approach without external dependencies (DEAP).
Implements selection, crossover, and mutation over parameter combinations.
"""

import random
import logging
from typing import Callable

import pandas as pd
import numpy as np
from app.analysis.backtest.engine import run_backtest

logger = logging.getLogger(__name__)


def genetic_optimize(
    df: pd.DataFrame,
    signal_generator: Callable,
    param_space: dict[str, dict],
    scoring: str = "sharpe_ratio",
    population_size: int = 50,
    generations: int = 30,
    mutation_rate: float = 0.2,
    crossover_rate: float = 0.7,
    elite_ratio: float = 0.1,
    top_n: int = 10,
) -> list[dict]:
    """Genetic algorithm optimization for strategy parameters.

    Args:
        df: OHLCV DataFrame
        signal_generator: Function(df, **params) -> (entry_signals, exit_signals)
        param_space: Dict of param_name -> {"type": "int"|"float", "low": x, "high": y, "step": s}
        scoring: Metric to maximize
        population_size: Number of individuals per generation
        generations: Number of evolutionary generations
        mutation_rate: Probability of mutating each gene
        crossover_rate: Probability of crossover between parents
        elite_ratio: Fraction of top individuals to carry forward unchanged
        top_n: Number of top results to return
    """

    def random_individual() -> dict:
        """Create a random parameter set."""
        params = {}
        for name, spec in param_space.items():
            if spec["type"] == "int":
                step = spec.get("step", 1)
                val = random.randrange(spec["low"], spec["high"] + 1, step)
                params[name] = val
            elif spec["type"] == "float":
                params[name] = round(
                    random.uniform(spec["low"], spec["high"]),
                    spec.get("decimals", 2),
                )
            elif spec["type"] == "categorical":
                params[name] = random.choice(spec["choices"])
        return params

    def evaluate(params: dict) -> float:
        """Evaluate fitness of a parameter set."""
        try:
            entry_signals, exit_signals = signal_generator(df, **params)
            bt = run_backtest(df, entry_signals, exit_signals)
            if bt.total_trades < 5:
                return -999.0
            return getattr(bt, scoring, bt.sharpe_ratio)
        except Exception:
            return -999.0

    def crossover(parent1: dict, parent2: dict) -> dict:
        """Uniform crossover between two parents."""
        child = {}
        for key in parent1:
            if random.random() < 0.5:
                child[key] = parent1[key]
            else:
                child[key] = parent2[key]
        return child

    def mutate(individual: dict) -> dict:
        """Mutate individual by randomly changing one or more parameters."""
        mutant = individual.copy()
        for name, spec in param_space.items():
            if random.random() < mutation_rate:
                if spec["type"] == "int":
                    step = spec.get("step", 1)
                    # Small perturbation
                    delta = random.choice([-step, step, -2 * step, 2 * step])
                    mutant[name] = max(spec["low"], min(spec["high"], mutant[name] + delta))
                elif spec["type"] == "float":
                    range_size = spec["high"] - spec["low"]
                    delta = random.gauss(0, range_size * 0.1)
                    mutant[name] = round(
                        max(spec["low"], min(spec["high"], mutant[name] + delta)),
                        spec.get("decimals", 2),
                    )
                elif spec["type"] == "categorical":
                    mutant[name] = random.choice(spec["choices"])
        return mutant

    # Initialize population
    population = [random_individual() for _ in range(population_size)]
    all_results: dict[str, dict] = {}  # key = str(params) -> result
    elite_count = max(1, int(population_size * elite_ratio))

    best_fitness_history = []

    for gen in range(generations):
        # Evaluate all individuals
        fitness_scores = []
        for ind in population:
            key = str(sorted(ind.items()))
            if key not in all_results:
                fit = evaluate(ind)
                all_results[key] = {"params": ind, "fitness": fit}
            fitness_scores.append((ind, all_results[key]["fitness"]))

        # Sort by fitness (descending)
        fitness_scores.sort(key=lambda x: x[1], reverse=True)
        best_fitness_history.append(fitness_scores[0][1])

        if gen % 10 == 0:
            logger.info(
                f"GA Gen {gen}/{generations}: best={fitness_scores[0][1]:.4f}, "
                f"mean={np.mean([f for _, f in fitness_scores]):.4f}"
            )

        # Selection: tournament selection
        def tournament_select(k: int = 3) -> dict:
            contestants = random.sample(fitness_scores, min(k, len(fitness_scores)))
            return max(contestants, key=lambda x: x[1])[0]

        # Create next generation
        new_population = []

        # Elitism: carry best individuals forward
        for i in range(elite_count):
            new_population.append(fitness_scores[i][0])

        # Fill rest with crossover and mutation
        while len(new_population) < population_size:
            if random.random() < crossover_rate:
                parent1 = tournament_select()
                parent2 = tournament_select()
                child = crossover(parent1, parent2)
            else:
                child = tournament_select()

            child = mutate(child)
            new_population.append(child)

        population = new_population

    # Collect all evaluated results
    evaluated = []
    for key, result in all_results.items():
        if result["fitness"] > -900:
            try:
                entry_signals, exit_signals = signal_generator(df, **result["params"])
                bt = run_backtest(df, entry_signals, exit_signals)
                evaluated.append({
                    "params": result["params"],
                    "metrics": {
                        "total_return": bt.total_return,
                        "annual_return": bt.annual_return,
                        "sharpe_ratio": bt.sharpe_ratio,
                        "sortino_ratio": bt.sortino_ratio,
                        "max_drawdown": bt.max_drawdown,
                        "win_rate": bt.win_rate,
                        "profit_factor": bt.profit_factor,
                        "total_trades": bt.total_trades,
                        "calmar_ratio": bt.calmar_ratio,
                    },
                    "backtest": bt,
                })
            except Exception:
                pass

    evaluated.sort(key=lambda x: x["metrics"].get(scoring, 0), reverse=True)
    return evaluated[:top_n]
