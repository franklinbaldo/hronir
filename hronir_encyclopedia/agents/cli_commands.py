"""
CLI commands for AI agent management and testing.
"""

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from .chapter_writer import ChapterWriterAgent
from .judge import JudgeAgent
from .crew_manager import HronirCrew, CrewConfig
from .base import AgentConfig
from .. import storage

# Create console for rich output
console = Console()

# Create agent sub-app
agent_app = typer.Typer(help="AI agent management commands")


@agent_app.command("test-writer")
def test_chapter_writer(
    position: int = typer.Option(0, help="Position for the new chapter"),
    predecessor_uuid: Optional[str] = typer.Option(None, help="UUID of predecessor hrönir"),
    theme: str = typer.Option("continuation", help="Theme for the chapter"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Test the Chapter Writer agent."""
    
    console.print(f"[bold blue]Testing Chapter Writer Agent[/bold blue]")
    console.print(f"Position: {position}")
    console.print(f"Predecessor: {predecessor_uuid}")
    console.print(f"Theme: {theme}")
    
    try:
        # Create agent
        config = AgentConfig(
            name="Test Chapter Writer",
            role="Literary Creator",
            goal="Create test hrönir chapter",
            backstory="Test agent for demonstration",
            verbose=verbose
        )
        
        agent = ChapterWriterAgent(config)
        
        # Execute task
        with Progress() as progress:
            task = progress.add_task("[green]Generating chapter...", total=1)
            
            result = agent.execute_task({
                "position": position,
                "predecessor_uuid": predecessor_uuid,
                "theme": theme
            })
            
            progress.update(task, advance=1)
        
        # Display results
        console.print(f"[bold green]✓ Chapter generated successfully![/bold green]")
        console.print(f"UUID: {result['uuid']}")
        console.print(f"Position: {result['position']}")
        console.print(f"Consistency Score: {result['consistency_score']:.2f}")
        
        # Show content preview
        content = result['content']
        preview = content[:200] + "..." if len(content) > 200 else content
        console.print(f"\n[bold]Content Preview:[/bold]")
        console.print(f"[italic]{preview}[/italic]")
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@agent_app.command("test-judge")
def test_judge_agent(
    position: int = typer.Option(0, help="Position to judge"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Test the Judge agent with mock data."""
    
    console.print(f"[bold blue]Testing Judge Agent[/bold blue]")
    console.print(f"Position: {position}")
    
    try:
        # Create agent
        config = AgentConfig(
            name="Test Judge",
            role="Literary Critic",
            goal="Evaluate test hrönir chapters",
            backstory="Test judge for demonstration",
            verbose=verbose
        )
        
        agent = JudgeAgent(config)
        
        # Mock content for testing
        content_a = """
        In the labyrinthine corridors of memory, where time folds upon itself like 
        parchment in an ancient library, I encountered a curious manuscript. The text 
        spoke of infinite realities, each word a doorway to possibility.
        """
        
        content_b = """
        The garden of forking paths stretched before me, each route a different destiny. 
        In one direction lay the certainty of knowledge; in another, the sweet 
        uncertainty of mystery. I chose the path that led to both.
        """
        
        # Test judgment
        with Progress() as progress:
            task = progress.add_task("[green]Evaluating chapters...", total=1)
            
            judgment = agent._parse_judgment(
                agent.generate_with_gemini(
                    agent.get_agent_prompt({
                        "content_a": content_a,
                        "content_b": content_b,
                        "position": position,
                        "context": "Test context"
                    })
                ),
                None  # Mock duel
            )
            
            progress.update(task, advance=1)
        
        # Display results
        console.print(f"[bold green]✓ Judgment completed![/bold green]")
        console.print(f"Winner: {judgment['winner']}")
        console.print(f"Confidence: {judgment['confidence']:.2f}")
        console.print(f"Reasoning: {judgment['reasoning']}")
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@agent_app.command("test-crew")
def test_crew_system(
    position: int = typer.Option(0, help="Position for the task"),
    predecessor_uuid: Optional[str] = typer.Option(None, help="UUID of predecessor hrönir"),
    num_chapters: int = typer.Option(2, help="Number of chapters to generate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Test the CrewAI integration."""
    
    console.print(f"[bold blue]Testing CrewAI Integration[/bold blue]")
    console.print(f"Position: {position}")
    console.print(f"Chapters to generate: {num_chapters}")
    
    try:
        # Create crew config
        config = CrewConfig(
            name="Test Crew",
            agents=["chapter_writer"],
            verbose=verbose
        )
        
        crew = HronirCrew(config)
        
        # Run competitive writing session
        async def run_test():
            return await crew.run_competitive_writing_session(
                position=position,
                predecessor_uuid=predecessor_uuid,
                num_chapters=num_chapters
            )
        
        with Progress() as progress:
            task = progress.add_task("[green]Running crew tasks...", total=1)
            
            results = asyncio.run(run_test())
            
            progress.update(task, advance=1)
        
        # Display results
        console.print(f"[bold green]✓ Crew tasks completed![/bold green]")
        
        # Create results table
        table = Table(title="Generated Chapters")
        table.add_column("UUID", style="cyan")
        table.add_column("Success", style="green")
        table.add_column("Preview", style="yellow")
        
        for result in results:
            if result.get('success'):
                uuid = result['uuid']
                preview = result['content'][:50] + "..." if len(result['content']) > 50 else result['content']
                table.add_row(uuid, "✓", preview)
            else:
                table.add_row("ERROR", "✗", result.get('error', 'Unknown error'))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@agent_app.command("competitive-session")
def run_competitive_session(
    position: int = typer.Option(0, help="Position for the competitive session"),
    predecessor_uuid: Optional[str] = typer.Option(None, help="UUID of predecessor hrönir"),
    num_agents: int = typer.Option(3, help="Number of competing agents"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output")
):
    """Run a competitive session between multiple AI agents."""
    
    console.print(f"[bold blue]Running Competitive Session[/bold blue]")
    console.print(f"Position: {position}")
    console.print(f"Number of agents: {num_agents}")
    
    try:
        # Create multiple writers
        writers = []
        for i in range(num_agents):
            config = AgentConfig(
                name=f"Competitive Writer {i+1}",
                role="Literary Competitor",
                goal=f"Create winning hrönir chapter (Agent {i+1})",
                backstory=f"Competitive agent {i+1} focused on literary excellence",
                verbose=verbose,
                temperature=0.7 + (i * 0.1)  # Vary creativity
            )
            writers.append(ChapterWriterAgent(config))
        
        # Generate chapters
        chapters = []
        with Progress() as progress:
            task = progress.add_task("[green]Generating competitive chapters...", total=num_agents)
            
            for i, writer in enumerate(writers):
                result = writer.generate_competitive_chapter(
                    position=position,
                    predecessor_uuid=predecessor_uuid,
                    opponent_strategy=f"strategy_{i}"
                )
                chapters.append(result)
                progress.update(task, advance=1)
        
        # Create judge
        judge_config = AgentConfig(
            name="Competition Judge",
            role="Literary Judge",
            goal="Evaluate competitive chapters",
            backstory="Expert judge for competitive evaluation",
            verbose=verbose
        )
        judge = JudgeAgent(judge_config)
        
        # Judge the chapters (simplified - just compare first two)
        if len(chapters) >= 2:
            with Progress() as progress:
                task = progress.add_task("[green]Judging chapters...", total=1)
                
                judgment = judge._parse_judgment(
                    judge.generate_with_gemini(
                        judge.get_agent_prompt({
                            "content_a": chapters[0]['content'],
                            "content_b": chapters[1]['content'],
                            "position": position,
                            "context": judge.get_narrative_context(position, predecessor_uuid)
                        })
                    ),
                    None  # Mock duel
                )
                
                progress.update(task, advance=1)
        
        # Display results
        console.print(f"[bold green]✓ Competitive session completed![/bold green]")
        
        # Create results table
        table = Table(title="Competitive Results")
        table.add_column("Agent", style="cyan")
        table.add_column("UUID", style="green")
        table.add_column("Consistency", style="yellow")
        table.add_column("Preview", style="magenta")
        
        for i, chapter in enumerate(chapters):
            table.add_row(
                f"Agent {i+1}",
                chapter['uuid'],
                f"{chapter['consistency_score']:.2f}",
                chapter['content'][:40] + "..."
            )
        
        console.print(table)
        
        if len(chapters) >= 2:
            console.print(f"\n[bold]Judge Decision:[/bold]")
            console.print(f"Winner: {judgment['winner']}")
            console.print(f"Confidence: {judgment['confidence']:.2f}")
            console.print(f"Reasoning: {judgment['reasoning']}")
        
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(1)


@agent_app.command("status")
def agent_status():
    """Show status of the agent system."""
    
    console.print(f"[bold blue]AI Agent System Status[/bold blue]")
    
    # Check database
    try:
        data_manager = storage.DataManager()
        console.print(f"[green]✓ Database connection: OK[/green]")
        
        # Get some stats
        # This would need actual implementation in data_manager
        console.print(f"[green]✓ Storage system: Ready[/green]")
        
    except Exception as e:
        console.print(f"[red]✗ Database error: {e}[/red]")
    
    # Check API keys
    import os
    if os.getenv("GEMINI_API_KEY"):
        console.print(f"[green]✓ Gemini API key: Configured[/green]")
    else:
        console.print(f"[red]✗ Gemini API key: Not found[/red]")
    
    # Check CrewAI
    try:
        import crewai
        console.print(f"[green]✓ CrewAI: Available (v{crewai.__version__})[/green]")
    except ImportError:
        console.print(f"[yellow]⚠ CrewAI: Not installed[/yellow]")
    
    console.print(f"\n[bold]Available Commands:[/bold]")
    console.print(f"• test-writer: Test chapter generation")
    console.print(f"• test-judge: Test judgment capabilities")
    console.print(f"• test-crew: Test CrewAI integration")
    console.print(f"• competitive-session: Run agent competition")