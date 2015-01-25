# =====================================================
# _nbutils.pyx
# ====================================================
from libc.stdlib cimport free, malloc, realloc

cdef class Stack:
    def __cinit__(self,SIZE_t capacity):
        self.capacity = capacity
        self.top = 0

        self.stack_ = <StackRecord*>malloc(self.capacity * sizeof(StackRecord))
        if self.stack_ == NULL:
            raise MemoryError()
    def __dealloc__(self):
        free(self.stack_)

    cdef bint is_empty(self) nogil:
        return self.top <= 0

    cdef int _resize(self) nogil:
        cdef StackRecord* stack = NULL
        cdef SIZE_t capacity = self.capacity * 2

        stack = <StackRecord*> realloc(
                self.stack_, self.capacity * sizeof(StackRecord))
       
        if stack == NULL:
            return -1
        else:
            self.stack_ = stack
            self.capacity = capacity
            return 0


    cdef int push(self, SIZE_t start, SIZE_t end, SIZE_t depth, 
                SIZE_t parent, SIZE_t index, SIZE_t n_node_features) nogil:
        cdef StackRecord* stack = NULL
        cdef SIZE_t top = self.top

        if top >= self.capacity:
            self.capacity *= 2
            stack = <StackRecord*> realloc(self.stack_,
                                           self.capacity * sizeof(StackRecord))
            if stack == NULL:
                # no free; __dealloc__ handles that
                return -1
            self.stack_ = stack

       
        stack = self.stack_
        stack[top].start = start
        stack[top].end   = end
        stack[top].depth = depth
        stack[top].parent= parent
        stack[top].index = index
        stack[top].n_node_features = n_node_features
       
        self.top = top + 1
        return 0 

    cdef int pop(self, StackRecord* sr) nogil:
        cdef SIZE_t top = self.top
        cdef StackRecord* stack = self.stack_

        if top <= 0:
            return -1

        sr[0] = stack[top-1]
        self.top = top-1

