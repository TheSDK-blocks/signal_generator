add wave -position insertpoint  \
sim:/tb_signal_generator/A \
sim:/tb_signal_generator/initdone \
sim:/tb_signal_generator/clock \
sim:/tb_signal_generator/Z \

run -all
