// C++ program for pasting text via clipboard + Ctrl+V
// Compile: g++ paste_text.cpp -o paste_text.exe -luser32
#include <windows.h>
#include <string>
#include <iostream>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        return 1;
    }
    
    std::string text = argv[1];
    
    // Open clipboard
    if (!OpenClipboard(NULL)) {
        return 1;
    }
    
    // Empty clipboard
    EmptyClipboard();
    
    // Allocate memory for text
    HGLOBAL hglb = GlobalAlloc(GMEM_MOVEABLE, text.size() + 1);
    if (hglb == NULL) {
        CloseClipboard();
        return 1;
    }
    
    // Lock and copy text
    char* lptstr = (char*)GlobalLock(hglb);
    memcpy(lptstr, text.c_str(), text.size() + 1);
    GlobalUnlock(hglb);
    
    // Set clipboard data
    SetClipboardData(CF_TEXT, hglb);
    CloseClipboard();
    
    // Wait a bit
    Sleep(100);
    
    // Send Ctrl+V
    keybd_event(VK_CONTROL, 0, 0, 0);
    Sleep(50);
    keybd_event('V', 0, 0, 0);
    Sleep(50);
    keybd_event('V', 0, KEYEVENTF_KEYUP, 0);
    Sleep(50);
    keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0);
    
    // Wait for paste to complete
    Sleep(200);
    
    return 0;
}
