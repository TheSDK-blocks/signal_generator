module signal_generator( input reset,
                 input A, 
                 output Z );
//reset does nothing
assign Z= !A;

endmodule
