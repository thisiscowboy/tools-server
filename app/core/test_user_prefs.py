from app.core.memory_service import MemoryService

ms = MemoryService()
# Set a preference
ms.set_user_preference("test_user", {"theme": "dark", "language": "en"})
# Get the preference
prefs = ms.get_user_preference("test_user")
print(f"Retrieved preferences: {prefs}")
