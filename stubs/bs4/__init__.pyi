# pylint: disable=unused-argument,line-too-long
from typing import Any, Dict, List, Optional, Union, Iterable, Iterator, TypeVar, overload, Callable, Pattern

T = TypeVar('T')

class Tag:
    name: str
    attrs: Dict[str, Any]
    contents: List[Any]
    string: Optional[str]

    def __init__(self, name: str, attrs: Optional[Dict[str, Any]] = None) -> None: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def __getitem__(self, key: str) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...
    def get_text(self, separator: str = "", strip: bool = False) -> str: ...
    def select(self, selector: str) -> List['Tag']: ...
    def select_one(self, selector: str) -> Optional['Tag']: ...
    def find_all(self, name: Optional[Union[str, List[str], Pattern, Callable]] = None, 
                attrs: Optional[Dict[str, Any]] = None, 
                recursive: bool = True, 
                text: Optional[Union[str, List[str], Pattern, Callable]] = None, 
                limit: Optional[int] = None, 
                **kwargs: Any) -> List['Tag']: ...
    def find(self, name: Optional[Union[str, List[str], Pattern, Callable]] = None, 
            attrs: Optional[Dict[str, Any]] = None, 
            recursive: bool = True, 
            text: Optional[Union[str, List[str], Pattern, Callable]] = None, 
            **kwargs: Any) -> Optional['Tag']: ...

class NavigableString(str):
    def get(self, key: str, default: Any = None) -> Any: ...
    def __getitem__(self, key: str) -> Any: ...
    def __setitem__(self, key: str, value: Any) -> None: ...

PageElement = Union[Tag, NavigableString]

class BeautifulSoup:
    def __init__(self, markup: str = "", features: str = "html.parser", 
                 builder: Any = None, parse_only: Any = None, 
                 from_encoding: Optional[str] = None, 
                 exclude_encodings: Optional[List[str]] = None, 
                 element_classes: Optional[Dict[str, Any]] = None, 
                 **kwargs: Any) -> None: ...
    def find_all(self, name: Optional[Union[str, List[str], Pattern, Callable]] = None, 
                attrs: Optional[Dict[str, Any]] = None, 
                recursive: bool = True, 
                text: Optional[Union[str, List[str], Pattern, Callable]] = None, 
                limit: Optional[int] = None, 
                **kwargs: Any) -> List[Tag]: ...
    def find(self, name: Optional[Union[str, List[str], Pattern, Callable]] = None, 
            attrs: Optional[Dict[str, Any]] = None, 
            recursive: bool = True, 
            text: Optional[Union[str, List[str], Pattern, Callable]] = None, 
            **kwargs: Any) -> Optional[Tag]: ...
    def select(self, selector: str) -> List[Tag]: ...
    def select_one(self, selector: str) -> Optional[Tag]: ...
