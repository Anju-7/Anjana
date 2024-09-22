#A trivia on Computer science
print("TRIVIA ON COMPUTER SCIENCE")
word=input("Do you want to play this game?\n")
if word.lower() != "yes":
    quit()
score=0
print("*Please enter 1 or 2*")
ans=input("Who is the world's first programmer?\n1.Grace Hopper\n2.Ada Lovelace\n")
if ans=='1':
    print("Incorrect!")
    
else:
    print("Correct!")
    score+=1
ans=input("What is the expansion of CPU?\n1.Central processing unit\n2.Computer Processing unit\n")
if ans=='1':
    print("Correct!")
    score+=1
else:
    print("Incorrect!")
ans=input("What is the expansion of GPU?\n1.grammar processing unit\n2.graphics Processing unit\n")
if ans=='1':
    print("Incorrect!")
   
else:
    print("Correct!")
    score+=1
    
ans=input("What is the expansion of TPU?\n1.Tensor processing unit\n2.Transfer Processing unit\n")
if ans=='1':
    print("Correct!")
    score+=1
else:
    print("Incorrect!")
ans=input("Who is the creator of python?\n1.Guido Van Rossum\n2.Charles Babbage\n")
if ans=='1':
    print("Correct!")
    score+=1
else:
    print("Incorrect!")
print("You have answered"+str(score)+"questions out of 5")
print("You scored",((score/5)*100),"percent in the trivia" )