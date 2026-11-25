.intel_syntax noprefix
.section .text
.global selector
selector:
    test rcx, rcx
    jz invalid
    cmp byte ptr [rcx], 0x72
    jne normal
    cmp byte ptr [rcx+1], 0x75
    jne normal
    cmp byte ptr [rcx+2], 0x73
    jne normal
    cmp byte ptr [rcx+3], 0
    jne normal
    lea rax, [rip+text_return]
    cmp rdx, rax
    je matched
    mov rax, qword ptr [rip+language_table]
    ret
normal:
    lea r8, [rip+language_table]
    mov r9d, 9
next_language:
    mov r10, qword ptr [r8]
    mov r11, rcx
compare:
    mov al, byte ptr [r11]
    cmp al, byte ptr [r10]
    jne mismatch
    test al, al
    je matched
    inc r11
    inc r10
    jmp compare
mismatch:
    add r8, 8
    dec r9d
    jne next_language
invalid:
    xor eax, eax
    ret
matched:
    mov rax, rcx
    ret
