#!/usr/bin/env python3
"""
علوم القرآن - Application Runner
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("علوم القرآن Platform")
    print("=" * 50)
    print()
    print("Starting server at: http://localhost:8000")
    print()
    print("Available pages:")
    print("  - Home:           http://localhost:8000/")
    print("  - Quran Browser:  http://localhost:8000/quran")
    print("  - Tafsir Compare: http://localhost:8000/tafsir")
    print("  - Qiraat:         http://localhost:8000/qiraat")
    print("  - Asbab al-Nuzul: http://localhost:8000/asbab")
    print()
    print("API Documentation:  http://localhost:8000/api/docs")
    print()
    print("=" * 50)

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
