#!/usr/bin/env python3
"""Demo script for LangGraph integration."""
import asyncio
import json
from pathlib import Path

from ai.graph.run import start_graph, resume_graph
from core.logging import logger

async def demo():
    """Run a demo of the LangGraph integration."""
    print("=" * 60)
    print("LangGraph Runtime Demo")
    print("=" * 60)
    
    # Test 1: Image generation workflow
    print("\n1. Testing image generation workflow...")
    result = await start_graph(
        session_id="demo_img_001",
        goal="Generate an image of a beautiful sunset over mountains",
        user_context={
            "user_id": "demo_user",
            "source": "demo"
        }
    )
    
    print(f"   Status: {result['status']}")
    print(f"   Session: {result['session_id']}")
    if result.get('artifacts'):
        print(f"   Artifacts: {result['artifacts']}")
    if result.get('error'):
        print(f"   Error: {result['error']}")
        
    # Check the report
    report_path = Path("data/graph/reports") / f"{result['session_id']}.json"
    if report_path.exists():
        with open(report_path) as f:
            report = json.load(f)
        print(f"   Steps completed: {report['steps_completed']}/{report['total_steps']}")
        
    # Test 2: Resume functionality
    print("\n2. Testing resume functionality...")
    resume_result = await resume_graph(
        session_id="demo_img_001",
        additional_context={"resumed": True}
    )
    print(f"   Resume status: {resume_result.get('status', 'N/A')}")
    
    # Test 3: Non-image workflow
    print("\n3. Testing generic task workflow...")
    result2 = await start_graph(
        session_id="demo_task_001",
        goal="Analyze customer feedback and generate insights",
        user_context={
            "user_id": "demo_user",
            "task_type": "analysis"
        }
    )
    
    print(f"   Status: {result2['status']}")
    print(f"   Session: {result2['session_id']}")
    
    print("\n" + "=" * 60)
    print("Demo completed!")
    print("Check ./data/graph/reports/ for execution reports")
    print("Check ./artifacts/ for generated artifacts")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(demo())